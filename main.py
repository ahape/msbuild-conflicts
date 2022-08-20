import sys, os, json, re

token_rx = re.compile(r"\((.*)\)\s+")
assemblies = {}

def get_dll_text(dll_path):
  return os.popen(f"ildasm /text {dll_path}").read()

def extract_token(line):
  return token_rx.search(line)[1].replace(" ", "").lower()

def extract_version(line):
  return line.split(" ")[-1].replace(":", ".")

def extract_module(line):
  return line.split(" ")[-1].replace(".exe", "").replace(".dll", "")

def update_assemblies(refs, module):
  for name, asm in refs.items():
    if name in assemblies:
      orig = assemblies[name]
      if not isinstance(orig["version"], list):
        orig["version"] = [orig["version"]]
      if asm["version"] not in orig["version"]:
        orig["version"].append(asm["version"])
      if not orig["publickeytoken"] and asm["publickeytoken"]:
        orig["publickeytoken"] = asm["publickeytoken"]
    else:
      assemblies[name] = asm
    if name != module:
      assemblies[name]["refs"].append({ "name": module, "version": asm["version"] })

def get_references_from_dll(dll_path):
  dll = get_dll_text(dll_path)
  refs = {}
  latest = None
  module = None
  
  for line in dll.splitlines():
    line = line.strip()

    if line.startswith(".assembly "):
      name = line.split(" ")[-1]
      latest = { "refs": [], "version": None, "publickeytoken": None, "name": name }
      refs[name] = latest
    elif latest is not None:
      if line.startswith(".publickeytoken "):
        latest["publickeytoken"] = extract_token(line)
      elif line.startswith(".ver "):
        latest["version"] = extract_version(line)
      elif line.startswith("}"):
        latest = None
    if line.startswith(".module "):
      module = extract_module(line)

  update_assemblies(refs, module)

if __name__ == "__main__":
  directory = "dlls/" # Default to test directory
  if not sys.argv[-1].endswith(".py"):
    directory = sys.argv[-1]
  print(f"Running for {directory}")
  for root, _, files in os.walk(directory):
    for file in files:
      if file.endswith(".exe") or file.endswith(".dll"):
        get_references_from_dll(os.path.join(root, file))

  print(json.dumps(assemblies, indent=2))

