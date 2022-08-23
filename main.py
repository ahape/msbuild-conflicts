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
csproj_rx = re.compile(r"\\([^\\]+)\.csproj")
assemblies = {}

class Node():
  def __init__(self, name, conflict=False):
    self.name = name
    self.conflict = conflict
    self.references = set()

  def __hash__(self):
    return id(self.name)

class Ref():
  def __init__(self, node, version="", is_primary=False):
    self.node = node
    self.version = version
    self.is_primary = is_primary

  def __hash__(self):
    return id(self.node.name + self.version)

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
    retval["version"] = parts[1].replace("Version=", "")
  if len(parts) > 3:
    retval["publicKeyToken"] = parts[3].replace("PublicKeyToken=", "")
  return retval

def parse_references_which_depend_on(line):
  fusion_name = ref_which_dep_rx.search(line)[1]
  return parse_fusion_name(fusion_name)

def find(arr, cb):
  for x in arr:
    if cb(x):
      return x

def parse_assembly_name(line):
  if match := dll_rx.search(line):
    return match[1]
  return parse_fusion_name(line.strip())["name"]

def get_node(nodes, name):
  if node := find(nodes, lambda x: x.name == name):
    return node
  node = Node(name)
  nodes.append(node)
  return node

def parse_project_name(line):
  start = line.index(" [")+2
  end = line.index("]")
  match = csproj_rx.search(line[start:end])
  if match:
    return match[1]

# Partial name of conflict instead of number
def parse_build_output(file_path, max_conflicts):
  nodes = []
  ref_num = 0
  root, ref, child, version = None, None, None, None
  with open(file_path) as f:
    for line in f.readlines():
      if not root and line.startswith("Project "):
        name = csproj_rx.search(line)[1]
        root = get_node(nodes, name)
      if "MSB3277:" in line:
        index = line.index("MSB3277:") + len("MSB3277:")
        line = line[index:] # Start at the beginning of the warning message
        if line.startswith(" Found conflicts between different versions of"):
          ref_num = 0
        elif line.startswith("     References which depend on"):
          proj = parse_project_name(line)
          ref_num += 1
          child = None
          asm = parse_references_which_depend_on(line)
          version = asm["version"]
          ref = get_node(nodes, asm["name"])
          ref.conflict = True
        elif ref and dep_on_rx.search(line):
          proj = parse_project_name(line)
          name = parse_assembly_name(line)
          child = get_node(nodes, name)
          ref.references.add(Ref(child, version, ref_num == 1))
        elif child and include_item_rx.search(line):
          proj = parse_project_name(line)
          line = line[:line.index(" [")]
          name = parse_assembly_name(line)
          grandchild = get_node(nodes, name)
          child.references.add(Ref(grandchild, version, ref_num == 1))
          grandchild.references.add(Ref(get_node(nodes, proj), version, ref_num == 1))
      elif ref and isinstance(max_conflicts, int):
        break
    else:
      ref = child = version = None
  for node in nodes:
    if len(node.references) == 0 and node.name != root.name:
      node.references.add(Ref(root))
  return nodes

def create_graph_simple(nodes):
  g = GV.Digraph(
    filename="Diagram",
    directory="out",
    format="svg")
  combos = set()
  for node in nodes:
    for ref in node.references:
      a = ref.node.name
      b = node.name
      if a != b and ((a,b) not in combos or (b,a) not in combos):
        combos.add((a,b))
        combos.add((b,a))
        if node.conflict:
          g.node(b, style="filled", fillcolor="salmon")
        if ref.version:
          g.edge(a, b, label=ref.version, color="blue" if ref.is_primary else "black")
        else:
          g.edge(a, b)
  g.attr(overlap="false")
  g.attr(splines="true")
  g.view()

def create_graph_complex():
  g = GV.Digraph(
    filename="Diagram",
    directory="out",
    format="svg")
  for asm in assemblies.values():
    for ref in asm["refs"]:
      g.edge(ref["name"], asm["name"])
  g.view()

def try_parse_int(x):
  try:
    return int(x)
  except:
    return None

if __name__ == "__main__":
  """
  if len(sys.argv) < 2:
    print("Need to supply out directory")
    raise SystemExit

  if len(sys.argv) == 3:
    build_output_file = sys.argv[-1]
    directory = sys.argv[-2]
  else:
    build_output_file = "build.txt"
    directory = sys.argv[-1]
  """
  build_output_file = sys.argv[-1]
  if max_conflicts := try_parse_int(build_output_file):
    build_output_file = sys.argv[-2]
  nodes = parse_build_output(build_output_file, max_conflicts)
  create_graph_simple(nodes)

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
  create_graph_complex()
  """
