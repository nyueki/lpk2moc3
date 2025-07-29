import json
import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from threading import Thread
import manager
from Core.lpk_loader import LpkLoader
from Core.utils import normalize, safe_mkdir

currentThread = None


class Win(ctk.CTk):

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("system")  # "dark" or "light" or "system"
        ctk.set_default_color_theme("blue")  # Windows 11-like accent
        self.title("LPK Model Extractor")
        self._width = 570
        self._height = 450
        self.geometry(f"{self._width}x{self._height}")
        self.resizable(width=False, height=False)
        self.inputPath = ctk.StringVar()
        self.outputPath = ctk.StringVar()
        self.configPath = ctk.StringVar()
        self.modelNameVar = ctk.StringVar(value="character")
        self.setupUI()
        manager.Log("Instructions\n"
                    "Models exported from Live2DViewerEX are in .wpk format\n"
                    "First, change the extension to .rar and extract to get .lpk and config.json files\n"
                    "If the model is not from EXViewer, you do not need to provide config.json\n"
                    "Model name can be customized, supports Chinese, but English is recommended")

    def setupUI(self):
        padding = 10
        self.grid_columnconfigure(1, weight=1)
        self.lbl_input = ctk.CTkLabel(self, text="LPK File")
        self.input = ctk.CTkEntry(self, textvariable=self.inputPath, width=300)
        self.getInput = ctk.CTkButton(self, text="Open File", command=self.getInputPath)
        self.lbl_output = ctk.CTkLabel(self, text="Output Path")
        self.output = ctk.CTkEntry(self, textvariable=self.outputPath, width=300)
        self.getOutput = ctk.CTkButton(self, text="Open Folder", command=self.getOutputPath)
        self.lbl_config = ctk.CTkLabel(self, text="config.json")
        self.config = ctk.CTkEntry(self, textvariable=self.configPath, width=300)
        self.getConfig = ctk.CTkButton(self, text="Select JSON File", command=self.getConfigPath)
        self.lbl_modelName = ctk.CTkLabel(self, text="Model Name")
        self.modelName = ctk.CTkEntry(self, textvariable=self.modelNameVar, width=300)
        self.getUnpack = ctk.CTkButton(self, text="Extract", command=self.Unpack, width=120)
        self.logArea = ctk.CTkTextbox(self, width=540, height=120)
        manager.LogArea = self.logArea

        # Place widgets with padding and spacing
        self.lbl_input.grid(row=0, column=0, padx=padding, pady=(padding, 0), sticky="w")
        self.input.grid(row=0, column=1, padx=padding, pady=(padding, 0), sticky="ew")
        self.getInput.grid(row=0, column=2, padx=padding, pady=(padding, 0))

        self.lbl_config.grid(row=1, column=0, padx=padding, pady=(padding, 0), sticky="w")
        self.config.grid(row=1, column=1, padx=padding, pady=(padding, 0), sticky="ew")
        self.getConfig.grid(row=1, column=2, padx=padding, pady=(padding, 0))

        self.lbl_output.grid(row=2, column=0, padx=padding, pady=(padding, 0), sticky="w")
        self.output.grid(row=2, column=1, padx=padding, pady=(padding, 0), sticky="ew")
        self.getOutput.grid(row=2, column=2, padx=padding, pady=(padding, 0))

        self.lbl_modelName.grid(row=3, column=0, padx=padding, pady=(padding, 0), sticky="w")
        self.modelName.grid(row=3, column=1, padx=padding, pady=(padding, 0), sticky="ew")

        self.logArea.grid(row=4, column=0, columnspan=3, padx=padding, pady=(padding, 0), sticky="ew")

        self.getUnpack.grid(row=5, column=1, padx=padding, pady=(padding, padding))

    def updateModelNameFromConfig(self):
        config_path = self.config.get()
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    x = json.load(f)
                self.modelNameVar.set(
                    x.get("title", "character").replace("\\", "").replace("/", "").replace(":", "").replace("?", "").replace("<", "").replace(">", "").replace("|", "")
                )
            except Exception as e:
                print(e)

    def getInputPath(self):
        filePath = filedialog.askopenfilename(filetypes=[("LPK", ".lpk")])
        if len(filePath) > 0:
            self.inputPath.set(filePath)
            # Auto-select config.json in the same folder
            config_path = os.path.join(os.path.dirname(filePath), "config.json")
            if os.path.exists(config_path):
                self.configPath.set(config_path)
                self.updateModelNameFromConfig()
            # Auto-select output folder
            output_folder = os.path.join(os.path.dirname(filePath), "output")
            self.outputPath.set(output_folder)

    def getOutputPath(self):
        filePath = filedialog.askdirectory()
        if len(filePath) > 0:
            self.outputPath.set(filePath)

    def getConfigPath(self):
        filePath = filedialog.askopenfilename(filetypes=[("JSON", ".json")])
        if len(filePath) > 0:
            self.configPath.set(filePath)
            # Auto-select .lpk in the same folder
            folder = os.path.dirname(filePath)
            for fname in os.listdir(folder):
                if fname.endswith(".lpk"):
                    lpk_path = os.path.join(folder, fname)
                    self.inputPath.set(lpk_path)
                    break
            # Auto-select output folder
            output_folder = os.path.join(folder, "output")
            self.outputPath.set(output_folder)
            self.updateModelNameFromConfig()

    def Unpack(self):
        global currentThread
        if currentThread is not None:
            messagebox.showwarning("LPK Model Extractor", "Extraction is already in progress, please wait")
            return
        self.logArea.configure(state="normal")
        self.logArea.delete("1.0", "end")
        currentThread = Thread(target=self._unpack)
        currentThread.start()

    def _unpack(self):
        global currentThread
        if len(self.output.get()) > 0 and len(self.input.get()) > 0:
            manager.Log(
                "LPK File: %s\nOutput Path: %s"
                % (self.input.get(), self.output.get())
            )
            try:
                loader = LpkLoader(self.input.get(), self.config.get())
                loader.extract(self.output.get())
                model_dir = os.path.join(self.outputPath.get(), normalize(self.modelNameVar.get()))
                manager.SetupModel(model_dir, self.modelNameVar.get())
                manager.Log("Extraction complete!")
                messagebox.showinfo("LPK Model Extractor", "Extraction successful!")
            except Exception as e:
                messagebox.showerror("LPK Model Extractor", "%s" % str(e))
                manager.Log("Error occurred: %s\nExtraction stopped." % e)
        else:
            messagebox.showerror(
                "LPK Model Extractor", "Missing input or output path"
            )
        currentThread = None


if __name__ == '__main__':
    w = Win()
    w.mainloop()
