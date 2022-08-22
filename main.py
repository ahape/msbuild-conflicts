import sys, os, json, re
import graphviz as GV
import xml.etree.ElementTree as ET

cache_file = "cache.json"
token_rx = re.compile(r"\((.*)\)\s+")
conflict_asms_rx = re.compile(r"'(.*?)'")
conflict_proj_rx = re.compile(r'Done building target "ImplicitlyExpandNETStandardFacades" in project "(.*)\.csproj"\.')
ref_which_dep_rx = re.compile(r'References which depend on "(.*?)"')
dep_on_rx = re.compile(r"^         \S")
include_item_rx = re.compile(r"^             \S")
dll_rx = re.compile(r"\\([^\\]+)\.(?:exe|dll)")

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

def create_graph(nodes):
  g = GV.Digraph(
    filename="Diagram",
    directory="out",
    #engine="neato",
    format="svg")

  """
  References which depend on X:
    Y (this is an immediate reference from the csproj)
      Project file item include which caused reference Y
        Z (this is something that Y depends on)
  for name in whitelist:
  """
  combos = set()
  for node in nodes:
    for ref in node.references:
      a_to_b = (ref.name, node.name)
      b_to_a = (node.name, ref.name)
      if a_to_b not in combos or b_to_a not in combos:
        combos.add(a_to_b)
        combos.add(b_to_a)
        g.edge(ref.name, node.name)

  #g.attr(overlap="false")
  #g.attr(splines="true")
  #g.unflatten(stagger=10).view()
  g.view()

def parse_fusion_name(fusion):
  parts = fusion.split(", ")
  retval = {}
  name = parts[0]
  if ":" in name:
    name = name[name.index(":") + 1:]
  name = name.replace(".dll", "").replace(".exe", "").replace("'", "")
  parts[0] = name
  retval["name"] = parts[0]
  if len(parts) > 1:
    retval["version"] = parts[1]
  if len(parts) > 3:
    retval["publicKeyToken"] = parts[3]
  return retval

def extract_assemblies_from_conflict_text(line):
  asms = conflict_asms_rx.search(line)
  return parse_fusion_name(asms[0]), parse_fusion_name(asms[1])

def parse_references_which_depend_on(line):
  fusion_name = ref_which_dep_rx.search(line)[1]
  return parse_fusion_name(fusion_name)

def find(arr, cb):
  for x in arr:
    if cb(x):
      return x

class Node():
  def __init__(self, name):
    self.name = name
    self.references = set()
    self.version = None

  def __hash__(self):
    return id(self.name)

def parse_build_output(file_path):
  nodes = []
  root = None
  child = None

  with open(file_path) as f:
    for line in f.readlines():
      if "MSB3277:" in line:
        index = line.index("MSB3277:") + len("MSB3277:")
        line = line[index:]
        if line.startswith("     References which depend on"):
          child = None
          asm = parse_references_which_depend_on(line)
          root = find(nodes, lambda x: x.name == asm["name"])
          if not root:
            root = Node(asm["name"])
            nodes.append(root)
        elif root and dep_on_rx.search(line):
          name = dll_rx.search(line)[1]
          child = find(nodes, lambda x: x.name == asm["name"])
          if not child:
            child = Node(name)
            nodes.append(child)
          if root.name != child.name:
            root.references.add(child)
        elif child and include_item_rx.search(line):
          line = line[:line.index(" [")]
          name = None
          if match := dll_rx.search(line):
            name = match[1]
          else:
            name = parse_fusion_name(line.strip())["name"]
          grandchild = find(nodes, lambda x: x.name == name)
          if not grandchild:
            grandchild = Node(name)
            nodes.append(grandchild)
          if child.name != grandchild.name:
            child.references.add(grandchild)
    else:
      root = child = None
  return nodes

if __name__ == "__main__":
  if len(sys.argv) < 2:
    print("Need to supply out directory")
    raise SystemExit

  if len(sys.argv) == 3:
    build_output_file = sys.argv[-1]
    directory = sys.argv[-2]
  else:
    build_output_file = None
    directory = sys.argv[-1]

  nodes = parse_build_output("tmp.txt")
  """
  print(f"Running for directory: {directory}")
  if not os.path.exists(cache_file):
    print(f"No cache file found. Disassembling all dlls in {directory}")
    load_assemblies(directory)
    cache_assemblies()
  else:
    print("Using cached assembly data")
    load_assemblies_from_cache()

  dump_config_data(directory)
  """
  create_graph(nodes)
