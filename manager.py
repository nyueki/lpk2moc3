import json
import os.path
import re
import shutil
import subprocess
from tkinter import Text, NORMAL, DISABLED, END

import motion_spec
from Core.utils import normalize, safe_mkdir  # Use updated utils


LogArea: Text | None = None


def rmdir(path):
    for i in os.listdir(path):
        p = os.path.join(path, i)
        if os.path.isdir(p):
            rmdir(p)
        else:
            os.remove(p)
    os.rmdir(path)


def Log(info):
    global LogArea
    LogArea.configure(state="normal")
    LogArea.insert("end", info + "\n")
    LogArea.see("end")
    LogArea.configure(state="disabled")


def organize_assets(model_dir: str):
    """
    Move motion .json files to 'motions' and sound files (.wav, .ogg) to 'sounds' folder.
    """
    motionPath = os.path.join(model_dir, "motions")
    soundPath = os.path.join(model_dir, "sounds")
    safe_mkdir(motionPath)
    safe_mkdir(soundPath)
    for fname in os.listdir(model_dir):
        fpath = os.path.join(model_dir, fname)
        if os.path.isfile(fpath):
            # Move motion files
            if fname.startswith("Motions_") and fname.endswith(".json"):
                shutil.move(fpath, os.path.join(motionPath, fname))
                Log(f"Moved motion file: {fname} -> motions/")
            # Move sound files
            elif fname.lower().endswith((".wav", ".ogg", ".mp3")):
                shutil.move(fpath, os.path.join(soundPath, fname))
                Log(f"Moved sound file: {fname} -> sounds/")


def organize_textures(model_dir: str, model_json_path: str, character_name: str):
    """
    Move texture files to a folder named <character>.<resolution> and update model3.json texture paths.
    """
    # Find texture files (png, jpg, etc.)
    texture_files = [f for f in os.listdir(model_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not texture_files:
        return

    # Determine resolution from the first texture file
    import PIL.Image
    first_texture_path = os.path.join(model_dir, texture_files[0])
    with PIL.Image.open(first_texture_path) as img:
        resolution = img.width  # Assuming square textures

    texture_folder = f"{character_name}.{resolution}"
    texture_folder_path = os.path.join(model_dir, texture_folder)
    safe_mkdir(texture_folder_path)

    # Move textures
    for tex_file in texture_files:
        shutil.move(os.path.join(model_dir, tex_file), os.path.join(texture_folder_path, tex_file))
        Log(f"Moved texture file: {tex_file} -> {texture_folder}/")

    # Update model3.json texture paths
    with open(model_json_path, "r", encoding="utf-8") as f:
        model_json = json.load(f)
    if "FileReferences" in model_json and "Textures" in model_json["FileReferences"]:
        model_json["FileReferences"]["Textures"] = [
            f"{texture_folder}/{os.path.basename(tex)}" for tex in model_json["FileReferences"]["Textures"]
        ]
        with open(model_json_path, "w", encoding="utf-8") as f:
            json.dump(model_json, f, ensure_ascii=False, indent=2)
        Log(f"Updated texture paths in {model_json_path}")


def SetupModel(model_dir: str, modelNameBase: str = None):
    motionPath, soundPath = CheckPath(model_dir)
    if not modelNameBase:
        modelNameBase = os.path.split(model_dir)[-1]
    modelJsonPathList: list = list()
    pat = re.compile("^model\d?.json$")
    for groupName in os.listdir(model_dir):
        if pat.findall(groupName):
            modelJsonPathList.append(os.path.join(model_dir, groupName))

    Log("Model Json Found: %s" % modelJsonPathList)
    removeList = list()
    for idx, modelJsonPath in enumerate(modelJsonPathList):
        modelName = normalize(modelNameBase + ("" if idx == 0 else str(idx+1)))
        x = json.load(open(modelJsonPath, 'r', encoding='utf-8'))
        motions = x["FileReferences"].get("Motions", [])
        for groupName in motions:
            Log("[Motion Group]: %s" % groupName)
            for idx, motion in enumerate(motions[groupName]):
                _File: str | None = motion.get("File", None)
                _Sound: str | None = motion.get("Sound", None)
                # motions/*.motion3.json
                if _File:
                    srcPath = os.path.join(model_dir, _File)
                    fileName = _File.replace("FileReferences_Motions", modelName).replace("_File_0", "").replace(".json", ".motion3.json")
                    targetPath = os.path.join(motionPath, fileName)
                    src = json.load(open(srcPath, 'r', encoding='utf-8'))
                    Log("CurveCount: %d" % src["Meta"]["CurveCount"])
                    Log("TotalSegmentCount: %d" % src["Meta"]["TotalSegmentCount"])
                    Log("TotalPointCount: %d" % src["Meta"]["TotalPointCount"])
                    with open(targetPath, 'w', encoding='utf-8') as f:
                        curve_count, segment_count, point_count = motion_spec.recount_motion(src)
                        Log("%d, %d, %d" % (curve_count, segment_count, point_count))
                        src["Meta"]["CurveCount"] = curve_count
                        src["Meta"]["TotalSegmentCount"] = segment_count
                        src["Meta"]["TotalPointCount"] = point_count
                        json.dump(src, f, ensure_ascii=False, indent=2)
                    removeList.append(srcPath)
                    Log("[Motion]: %s >>> %s" % (_File, targetPath))
                    x["FileReferences"]["Motions"][groupName][idx]["File"] = "motions/" + fileName
                # sounds/*.wav
                if _Sound:
                    srcPath = os.path.join(model_dir, _Sound)
                    fileName = _Sound.replace("FileReferences_Motions", modelName).replace("_Sound_0", "")
                    fileName = os.path.splitext(fileName)[0] + ".wav"
                    targetPath = os.path.join(soundPath, fileName)
                    # Use system ffmpeg instead of embedded
                    cmd = "ffmpeg -i \"%s\" -ac 1 \"%s\" -y -v quiet" % (srcPath, targetPath)
                    process = subprocess.Popen(
                        cmd, shell=True,
                        stderr=subprocess.PIPE
                    )
                    out = process.stderr.read().decode('utf-8', errors='ignore').strip("\n")
                    Log("[ffmpeg]: %s" % out)
                    process.kill()
                    process.wait()
                    removeList.append(srcPath)
                    Log("[Sound]: %s >>> %s" % (_Sound, targetPath))
                    x["FileReferences"]["Motions"][groupName][idx]["Sound"] = "sounds/" + fileName
        # link hitAreas with motion groups
        for idx, hitArea in enumerate(x.get("HitAreas", [])):
            if hitArea.get("Motion", None) is not None:
                x["HitAreas"][idx]["Name"] = hitArea["Motion"].split(":")[0]

        if x.get("Controllers", None) is not None:
            if x["Controllers"].get("ParamHit", None) is not None:
                if x["Controllers"]["ParamHit"].get("Items", None) is not None:
                    for idx2, item in enumerate(x["Controllers"]["ParamHit"]["Items"]):
                        if item.get("EndMtn", None) is not None:
                            x["HitAreas"].append(
                                {
                                    "Name": item.get("EndMtn"),
                                    "Id": item.get("Id")
                                }
                            )
        # save changes to model3.json
        model3_path = os.path.join(model_dir, modelName + ".model3.json")
        with open(model3_path, "w", encoding='utf-8') as f:
            json.dump(x, f, ensure_ascii=False, indent=2)

        # Organize textures and update model3.json
        organize_textures(model_dir, model3_path, modelName)

        if os.path.exists(modelJsonPath):
            os.remove(modelJsonPath)
        for i in set(removeList):
            Log("removing: %s" % i)
            if os.path.exists(i) and i not in x.get("Pose", ""):
                os.remove(i)
        new_dir = os.path.join(os.path.split(model_dir)[0], modelName)
        # Only rename if the target is different from the source
        if os.path.abspath(model_dir) != os.path.abspath(new_dir):
            if os.path.exists(new_dir):
                rmdir(new_dir)
            os.rename(model_dir, new_dir)
    # After all processing, organize assets
    organize_assets(model_dir)


def CheckPath(model_dir: str):
    motionPath = os.path.join(model_dir, "motions")
    soundPath = os.path.join(model_dir, "sounds")
    if not os.path.exists(motionPath):
        os.makedirs(motionPath)
    if not os.path.exists(soundPath):
        os.makedirs(soundPath)
    return motionPath, soundPath


if __name__ == '__main__':
    SetupModel("path to model dir", "model name")