import sys, os, json, re
import graphviz as GV
import xml.etree.ElementTree as ET

cache_file = "cache.json"
ver_rx = re.compile(r"\d+\.\d+\.\d+\.\d+")
token_rx = re.compile(r"\((.*)\)\s+")
no_version = "0.0.0.0"
assemblies = {}
configs = []
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
      if not orig["version"] and asm["version"]:
        orig["version"] = asm["version"]
      if not orig["publickeytoken"] and asm["publickeytoken"]:
        orig["publickeytoken"] = asm["publickeytoken"]
    else:
      assemblies[name] = asm
    if name != module:
      this = assemblies[name]
      # Want to just default nulls to something
      this["refs"].append({ "name": module, "version": asm["version"] or this["version"] })
  if module in assemblies:
    assemblies[module]["deps"] += [{ 
      "name": v["name"],
      "version": v["version"]
    } for v in refs.values() if v["name"] != module]

def get_references_from_dll(dll_path):
  dll = get_dll_text(dll_path)
  refs = {}
  latest = None
  module = None

  for line in dll.splitlines():
    line = line.strip()
    if line.startswith(".assembly "):
      name = line.split(" ")[-1]
      latest = { "refs": [], "deps": [], "version": no_version, "publickeytoken": None, "name": name }
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

def optimize_assemblies():
  singles = {}
  copy = assemblies.copy()
  copy.pop("mscorlib")
  copy.pop("netstandard")
  copy.pop("System")
  copy.pop("System.Core")

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
    new_deps = []
    for ref in asm["deps"]:
      if ref["name"] in copy:
        new_deps.append(ref)
    asm["deps"] = new_deps

  # Squash (group) single references
  for k, v in copy.copy().items():
    if len(v["refs"]) == 1 and len(v["deps"]) == 0:
      name = v["refs"][0]["name"]
      if name not in singles:
        singles[name] = v.copy()
      else:
        singles[name]["name"] += "\n" + k
      copy.pop(k)
  for asm in singles.values():
    copy[asm["name"]] = asm

  return copy

def parse_config(file):
  root = ET.parse(file).getroot()
  xmlns = "{urn:schemas-microsoft-com:asm.v1}"
  bindings = []
  for el in root.findall(f".//{xmlns}dependentAssembly"):
    identity = el.find(f".//{xmlns}assemblyIdentity")
    redirect = el.find(f".//{xmlns}bindingRedirect")
    if ET.iselement(identity) and ET.iselement(redirect):
      old_value = redirect.get("oldVersion")
      binding = {
        "name": identity.get("name"),
        "new": redirect.get("newVersion"),
      }
      if "-" in old_value:
        binding["old_range"] = old_value.split("-")
      else:
        binding["old"] = old_value
      bindings.append(binding)
  return bindings

def load_config_data(directory):
  global configs
  for root, _, files in os.walk(directory):
    for file in files:
      if file.endswith(".config"):
        configs += parse_config(os.path.join(root, file))
  # Return unique
  uniq, res = [], []
  for x in configs:
    if x["name"] not in uniq:
      uniq.append(x["name"])
      res.append(x)
  res.sort(key=lambda x: x["name"])

def find(arr, cb):
  for e in arr:
    if cb(e):
      return e

def ver_str_to_tuple(ver_str):
  return tuple(int(x) for x in ver_str.split("."))

def tuple_to_ver_str(tup):
  return ".".join(str(x) for x in tup)

def is_implicit_version(asm):
  return asm["version"] == no_version

# TODO Take into acct primary ref?
def get_redirect_version(ref, version, asm):
  version_tup = ver_str_to_tuple(version)
  config = find(configs, lambda x: x["name"] == asm["name"])
  if not config:
    return ref["version"]
  if "old_range" in config:
    fro, to = config["old_range"]
    if ver_str_to_tuple(fro) <= version_tup and ver_str_to_tuple(to) >= version_tup:
      return config["new"]
  if "old" in config:
    if ver_str_to_tuple(config["old"]) == version_tup:
      return config["new"]
  return ref["version"]

def create_graph():
  g = GV.Digraph(
    filename="Diagram",
    directory="out",
    #engine="neato",
    format="svg")
  
  """
  for asm in optimize_assemblies().values():
  """
  for asm in assemblies.values():
    refs = asm["refs"]
    ver = asm["version"]
    label = not all(is_implicit_version(r) or get_redirect_version(r, ver, asm) == ver for r in refs)
    for ref in refs:
      g.edge(ref["name"], asm["name"], label=ref["version"] if label else None)

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

  load_config_data(directory)
  create_graph()
