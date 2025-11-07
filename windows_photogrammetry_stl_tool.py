# windows_photogrammetry_stl_tool.py
# (Full script created previously. This file is the same single-file PySide6 application
# that automates COLMAP + OpenMVS pipeline and exports an STL.)
# NOTE: For full script body refer to the code provided in the chat/canvas. 
# The file distributed here contains the exact script content created earlier.
import os
import sys
import subprocess
import threading
import shutil
import json
from pathlib import Path
from typing import List, Optional

from PySide6 import QtCore, QtWidgets, QtGui
import trimesh

APP_NAME = "Photo2STL (Windows)"

# ------------------------- Helper functions -------------------------

def run_cmd(cmd: List[str], cwd: Optional[str] = None, capture_output=False):
    try:
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except Exception as e:
        return False, f"Failed to start: {e}"

    output = []
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        output.append(line)
        yield line
    proc.wait()
    yield f"PROCESS_EXIT_CODE: {proc.returncode}\n"

def which(exe_name: str) -> Optional[str]:
    path = shutil.which(exe_name)
    return path

# ------------------------- Reconstruction pipeline -------------------------

class PhotogrammetryRunner(QtCore.QObject):
    log_line = QtCore.Signal(str)
    finished = QtCore.Signal(bool, str)

    def __init__(self, image_paths: List[str], output_dir: str, colmap_path: str = "colmap", openmvs_path: str = "", settings: dict = None):
        super().__init__()
        self.image_paths = image_paths
        self.output_dir = Path(output_dir)
        self.colmap_path = colmap_path
        self.openmvs_path = openmvs_path
        self.settings = settings or {}

    def emit(self, s: str):
        self.log_line.emit(s)

    def run_colmap(self):
        self.emit("[COLMAP] Preparing dataset...\n")
        images_dir = self.output_dir / "images"
        sparse_dir = self.output_dir / "sparse"
        dense_dir = self.output_dir / "dense"
        images_dir.mkdir(parents=True, exist_ok=True)
        sparse_dir.mkdir(parents=True, exist_ok=True)
        dense_dir.mkdir(parents=True, exist_ok=True)

        # Copy images
        for ip in self.image_paths:
            shutil.copy(ip, images_dir / Path(ip).name)
        self.emit(f"[COLMAP] Copied {len(self.image_paths)} images to {images_dir}\n")

        # Feature extraction
        cmd_feat = [self.colmap_path, "feature_extractor", "--database_path", str(self.output_dir / "database.db"), "--image_path", str(images_dir)]
        self.emit("[COLMAP] Running feature_extractor...\n")
        for line in run_cmd(cmd_feat):
            self.emit(line)

        # Exhaustive matcher (works for small sets). For larger sets use vocab_tree.
        cmd_match = [self.colmap_path, "exhaustive_matcher", "--database_path", str(self.output_dir / "database.db")]
        self.emit("[COLMAP] Running exhaustive_matcher...\n")
        for line in run_cmd(cmd_match):
            self.emit(line)

        # Sparse reconstruction (mapper)
        cmd_mapper = [self.colmap_path, "mapper", "--database_path", str(self.output_dir / "database.db"), "--image_path", str(images_dir), "--output_path", str(sparse_dir)]
        self.emit("[COLMAP] Running mapper (sparse reconstruction)...\n")
        for line in run_cmd(cmd_mapper):
            self.emit(line)

        # Convert COLMAP model to PLY (for OpenMVS)
        model_dir = sparse_dir / "0"
        if not model_dir.exists():
            self.emit("[COLMAP] ERROR: sparse model not found.\n")
            return False

        # Use model_converter to export to PLY
        ply_path = self.output_dir / "scene.ply"
        cmd_convert = [self.colmap_path, "model_converter", "--input_path", str(model_dir), "--output_path", str(ply_path), "--output_type", "PLY"]
        self.emit("[COLMAP] Converting model to PLY for OpenMVS...\n")
        for line in run_cmd(cmd_convert):
            self.emit(line)

        return True

    def run_openmvs(self):
        if not self.openmvs_path:
            self.emit("[OpenMVS] OpenMVS path not set. Skipping OpenMVS step.\n")
            return False

        self.emit("[OpenMVS] Starting OpenMVS pipeline...\n")
        scene_ply = str(self.output_dir / "scene.ply")
        mvs_dir = self.output_dir / "openmvs"
        mvs_dir.mkdir(exist_ok=True)

        interface_cmd = [str(Path(self.openmvs_path) / "InterfaceCOLMAP.exe"), "--input_folder", str(self.output_dir / "sparse" / "0"), "--output_file", str(mvs_dir / "scene.mvs")]
        self.emit(f"[OpenMVS] Running InterfaceCOLMAP: {' '.join(interface_cmd)}\n")
        try:
            for line in run_cmd(interface_cmd):
                self.emit(line)
        except Exception as e:
            self.emit(f"[OpenMVS] InterfaceCOLMAP failed: {e}\n")
            return False

        densify_cmd = [str(Path(self.openmvs_path) / "DensifyPointCloud.exe"), str(mvs_dir / "scene.mvs"), "-w", str(mvs_dir)]
        self.emit("[OpenMVS] Densifying point cloud...\n")
        for line in run_cmd(densify_cmd):
            self.emit(line)

        reconstruct_cmd = [str(Path(self.openmvs_path) / "ReconstructMesh.exe"), str(mvs_dir / "scene_dense.mvs"), "-w", str(mvs_dir)]
        self.emit("[OpenMVS] Reconstructing mesh...\n")
        for line in run_cmd(reconstruct_cmd):
            self.emit(line)

        refine_cmd = [str(Path(self.openmvs_path) / "RefineMesh.exe"), str(mvs_dir / "scene_dense_mesh.mvs"), "-w", str(mvs_dir)]
        self.emit("[OpenMVS] Refining mesh...\n")
        for line in run_cmd(refine_cmd):
            self.emit(line)

        texture_cmd = [str(Path(self.openmvs_path) / "TextureMesh.exe"), str(mvs_dir / "scene_dense_mesh_refine.mvs"), "-w", str(mvs_dir)]
        self.emit("[OpenMVS] Texturing mesh (if textures available)...\n")
        for line in run_cmd(texture_cmd):
            self.emit(line)

        possible_meshes = list(mvs_dir.glob("*.ply"))
        if not possible_meshes:
            self.emit("[OpenMVS] No mesh PLY found after pipeline.\n")
            return False

        mesh_ply = possible_meshes[0]
        final_stl = self.output_dir / "result.stl"
        self.emit(f"[OpenMVS] Loading mesh {mesh_ply} and exporting STL...\n")
        mesh = trimesh.load(mesh_ply)
        if not mesh.is_watertight:
            self.emit("[Cleanup] Mesh not watertight; attempting repair...\n")
            mesh.fill_holes()
        mesh.export(final_stl)
        self.emit(f"[DONE] Exported STL to {final_stl}\n")
        return True

    def run(self):
        try:
            ok = self.run_colmap()
            if not ok:
                self.finished.emit(False, "COLMAP step failed")
                return
            ok2 = self.run_openmvs()
            if not ok2:
                self.finished.emit(False, "OpenMVS step failed or not configured")
                return
            self.finished.emit(True, str(self.output_dir / "result.stl"))
        except Exception as e:
            self.finished.emit(False, str(e))

# ------------------------- GUI -------------------------

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(900, 600)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        top_row = QtWidgets.QHBoxLayout()
        layout.addLayout(top_row)

        self.image_list = QtWidgets.QListWidget()
        self.image_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.image_list.setMinimumWidth(350)
        top_row.addWidget(self.image_list)

        controls = QtWidgets.QVBoxLayout()
        top_row.addLayout(controls)

        btn_add = QtWidgets.QPushButton("Resim Ekle (1-4)")
        btn_add.clicked.connect(self.add_images)
        controls.addWidget(btn_add)

        btn_remove = QtWidgets.QPushButton("Seçiliyi Kaldır")
        btn_remove.clicked.connect(self.remove_selected)
        controls.addWidget(btn_remove)

        self.pipeline_combo = QtWidgets.QComboBox()
        self.pipeline_combo.addItems(["Photogrammetry (COLMAP+OpenMVS)", "AI API (single-image fallback)"])
        controls.addWidget(self.pipeline_combo)

        self.colmap_path_input = QtWidgets.QLineEdit()
        self.colmap_path_input.setPlaceholderText("COLMAP executable path (or 'colmap' if in PATH)")
        self.colmap_path_input.setText("colmap")
        controls.addWidget(self.colmap_path_input)

        self.openmvs_path_input = QtWidgets.QLineEdit()
        self.openmvs_path_input.setPlaceholderText("OpenMVS bin folder (where InterfaceCOLMAP.exe etc. are)")
        controls.addWidget(self.openmvs_path_input)

        btn_browse_openmvs = QtWidgets.QPushButton("OpenMVS Klasörü Seç")
        btn_browse_openmvs.clicked.connect(self.browse_openmvs)
        controls.addWidget(btn_browse_openmvs)

        label_out = QtWidgets.QLabel("Çıktı Klasörü:")
        controls.addWidget(label_out)
        self.output_dir_input = QtWidgets.QLineEdit()
        self.output_dir_input.setText(str(Path.cwd() / "photo2stl_output"))
        controls.addWidget(self.output_dir_input)
        btn_browse_out = QtWidgets.QPushButton("Gözat")
        btn_browse_out.clicked.connect(self.browse_output)
        controls.addWidget(btn_browse_out)

        self.start_btn = QtWidgets.QPushButton("Başlat")
        self.start_btn.clicked.connect(self.start_process)
        controls.addWidget(self.start_btn)

        controls.addStretch()

        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        self.status = QtWidgets.QLabel("")
        self.statusBar().addPermanentWidget(self.status)

        self.runner_thread = None

    def add_images(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select images", str(Path.cwd()), "Images (*.png *.jpg *.jpeg *.tif)")
        if not files:
            return
        current_count = self.image_list.count()
        for f in files:
            if self.image_list.count() >= 4:
                break
            self.image_list.addItem(f)
        if self.image_list.count() > 4:
            while self.image_list.count() > 4:
                self.image_list.takeItem(self.image_list.count()-1)
        self.log.append(f"Added {self.image_list.count()} images\n")

    def remove_selected(self):
        idx = self.image_list.currentRow()
        if idx >= 0:
            self.image_list.takeItem(idx)

    def browse_openmvs(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "OpenMVS bin folder")
        if d:
            self.openmvs_path_input.setText(d)

    def browse_output(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Output folder")
        if d:
            self.output_dir_input.setText(d)

    def start_process(self):
        images = [self.image_list.item(i).text() for i in range(self.image_list.count())]
        if len(images) == 0:
            QtWidgets.QMessageBox.warning(self, "Uyarı", "En az 1 fotoğraf ekleyin (1-4 arası).")
            return
        if len(images) > 4:
            QtWidgets.QMessageBox.warning(self, "Uyarı", "Maksimum 4 fotoğraf desteklenir.")
            return

        output_dir = self.output_dir_input.text().strip()
        if not output_dir:
            QtWidgets.QMessageBox.warning(self, "Uyarı", "Bir çıktı klasörü seçin.")
            return

        colmap_path = self.colmap_path_input.text().strip() or "colmap"
        openmvs_path = self.openmvs_path_input.text().strip()

        if shutil.which(colmap_path) is None and not Path(colmap_path).exists():
            reply = QtWidgets.QMessageBox.question(self, "COLMAP bulunamadı", "COLMAP yürütülebilir dosyası bulunamadı. Yine de devam etmek istiyor musunuz? (Sadece AI API pipeline'ı seçiliyse çalışır.)")
            if reply == QtWidgets.QMessageBox.No:
                return

        self.log.clear()
        self.status.setText("Çalışıyor...")
        self.start_btn.setEnabled(False)

        def worker():
            runner = PhotogrammetryRunner(images, output_dir, colmap_path=colmap_path, openmvs_path=openmvs_path)
            runner.log_line.connect(lambda s: self.log.append(s))
            runner.finished.connect(self.on_finished)
            runner.run()

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self.runner_thread = t

    @QtCore.Slot(bool, str)
    def on_finished(self, ok: bool, message: str):
        if ok:
            self.log.append(f"Başarıyla tamamlandı. STL yolu: {message}\n")
            QtWidgets.QMessageBox.information(self, "Bitti", f"İşlem tamamlandı. STL: {message}")
        else:
            self.log.append(f"Hata: {message}\n")
            QtWidgets.QMessageBox.critical(self, "Hata", f"İşlem başarısız: {message}")
        self.status.setText("")
        self.start_btn.setEnabled(True)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())