import sys, os, json, re
import graphviz as GV

cache_file = "cache.json"
token_rx = re.compile(r"\((.*)\)\s+")
assemblies = {}
root = None

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
      if not isinstance(orig["version"], list) and orig["version"] != asm["version"]:
        orig["version"] = [orig["version"], asm["version"]]
      if isinstance(orig["version"], list) and asm["version"] not in orig["version"]:
        orig["version"].append(asm["version"])
      if not orig["publickeytoken"] and asm["publickeytoken"]:
        orig["publickeytoken"] = asm["publickeytoken"]
    else:
      assemblies[name] = asm
    if name != module:
      asm["refs"].append({ "name": module, "version": asm["version"] })

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
    f.write(json.dumps(assemblies))

def optimize_assemblies():
  singles = {}
  copy = assemblies.copy()
  copy.pop("mscorlib")
  copy.pop("System")
  copy.pop("netstandard")

  # Squash (group) single references
  for k, v in copy.copy().items():
    if len(v["refs"]) == 1:
      name = v["refs"][0]["name"]
      if name not in singles:
        singles[name] = v.copy()
      else:
        singles[name]["name"] += "\n" + k
      copy.pop(k)
  for asm in singles.values():
    copy[asm["name"]] = asm

  # Get rid of things not referenced
  for k, v in copy.copy().items():
    if len(v["refs"]) == 0 and k != root:
      copy.pop(k)

  for asm in copy.values():
    new_refs = []
    for ref in asm["refs"]:
      if ref["name"] in copy:
        new_refs.append(ref)
    asm["refs"] = new_refs

  return copy

def create_graph():
  g = GV.Digraph(
    filename="Diagram",
    directory="out",
    #engine="neato",
    format="svg")
  
  for asm in optimize_assemblies().values():
    for ref in asm["refs"]:
      g.edge(ref["name"], asm["name"])

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
    print("No cache file found. Disassembling all dlls in {directory}")
    load_assemblies(directory)
    cache_assemblies()
  else:
    print("Using cached assembly data")
    load_assemblies_from_cache()

  create_graph()

  #print(json.dumps(assemblies, indent=2))
