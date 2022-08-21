import sys, os, json, re
import graphviz as GV
import xml.etree.ElementTree as ET

cache_file = "cache.json"
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
      if orig["version"] == "0.0.0.0" and asm["version"] != "0.0.0.0": # Take strong over weak
        orig["version"] = asm["version"]
      if not orig["publickeytoken"] and asm["publickeytoken"]: # Take strong over weak
        orig["publickeytoken"] = asm["publickeytoken"]
    else:
      assemblies[name] = asm
    if name != module:
      orig = assemblies[name]
      # Want to just default nulls to something
      orig["refs"].append({ "name": module, "version": asm["version"] })
  if module in assemblies:
    assemblies[module]["deps"] += [{ 
      "name": v["name"],
      "version": v["version"]
    } for v in refs.values() if v["name"] != module]

def get_references_from_dll(dll_path):
  dll = get_dll_text(dll_path)
  refs = {}
  latest, module = None, None

  for line in dll.splitlines():
    line = line.strip()
    if line.startswith(".assembly "):
      name = line.split(" ")[-1]
      latest = { "refs": [], "deps": [], "version": "0.0.0.0", "publickeytoken": None, "name": name }
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

def load_assemblies(directory):
  for root, _, files in os.walk(directory):
    for file in files:
      if file.endswith(".exe") or file.endswith(".dll"):
        get_references_from_dll(os.path.join(root, file))

def load_assemblies_from_cache():
  global assemblies
  with open(cache_file) as f:
    assemblies = json.loads(f.read())

def cache_assemblies():
  with open(cache_file, "w") as f:
    f.write(json.dumps(assemblies, indent=2))

def parse_config(file):
  root = ET.parse(file).getroot()
  xmlns = "{urn:schemas-microsoft-com:asm.v1}"
  bindings = []
  for el in root.findall(f".//{xmlns}dependentAssembly"):
    identity = el.find(f".//{xmlns}assemblyIdentity")
    redirect = el.find(f".//{xmlns}bindingRedirect")
    if ET.iselement(identity) and ET.iselement(redirect):
      bindings.append({
        "name": identity.get("name"),
        "oldVersion": redirect.get("oldVersion"),
        "newVersion": redirect.get("newVersion"),
      })
  return bindings

def dump_config_data(directory):
  configs = {}
  for root, _, files in os.walk(directory):
    for file in files:
      if file.endswith(".config"):
        configs[file] = parse_config(os.path.join(root, file))
  with open("out/configs.json", "w") as f:
    f.write(json.dumps(configs, indent=2))

def create_graph():
  g = GV.Digraph(
    filename="Diagram",
    directory="out",
    #engine="neato",
    format="svg")
  
  for asm in assemblies.values():
    for ref in asm["refs"]:
      g.edge(ref["name"], asm["name"], label=ref["version"])

  #g.attr(overlap="false")
  #g.attr(splines="true")
  #g.unflatten(stagger=10).view()
  g.view()

if __name__ == "__main__":
  if len(sys.argv) < 3:
    print("Need to supply out directory and name of .NET project")
    raise SystemExit

  directory = sys.argv[-2]
  root = sys.argv[-1]

  print(f"Running for directory: {directory}")
  if not os.path.exists(cache_file):
    print(f"No cache file found. Disassembling all dlls in {directory}")
    load_assemblies(directory)
    cache_assemblies()
  else:
    print("Using cached assembly data")
    load_assemblies_from_cache()

  dump_config_data(directory)
  create_graph()
