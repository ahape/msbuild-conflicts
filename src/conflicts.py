import re, os, sys, tempfile
import graphviz as GV

ref_which_dep_rx = re.compile(r'References which depend on "(.*?)"')
conflict_dep_rx = re.compile(r"^         \S")
conflict_dep_dep_rx = re.compile(r"^             \S")
dll_rx = re.compile(r"\\([^\\]+)\.(?:exe|dll)")
csproj_rx = re.compile(r"\\([^\\]+)\.csproj")

class Node():
  def __init__(self, name, is_conflict=False):
    self.name = name
    self.is_conflict = is_conflict
    self.is_root_proj = False
    self.references = set()
  def __hash__(self):
    return id(self.name)

class Ref(Node):
  def __init__(self, node, version="", is_primary=False): # TODO: Use **kwargs
    super().__init__(node.name)
    self.version = version
    self.is_root_proj = node.is_root_proj
    self.is_primary = is_primary
  def __hash__(self):
    return super.__hash__(self)

class Assembly():
  def __init__(self):
    self.name = None
    self.version = None

def parse_fusion_name(fusion):
  parts = fusion.split(", ")
  asm = Assembly()
  name = parts[0]
  if ":" in name:
    name = name[name.index(":") + 1:]
  asm.name = name.replace(".dll", "").replace(".exe", "").replace("'", "")
  if len(parts) > 1:
    asm.version = parts[1].replace("Version=", "")
  return asm

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
  return parse_fusion_name(line.strip()).name

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

def trim_msberr_line(line):
  index = line.index("MSB3277:") + len("MSB3277:")
  return line[index:]

def strip_proj_portion(line):
  return line[:line.index(" [")]

def parse_build_output(build_output):
  nodes = []
  ref_num = 0
  root_proj, conflict, ref, version = None, None, None, None
  for line in build_output.splitlines():
    if not root_proj and line.startswith("Project "):
      name = csproj_rx.search(line)[1]
      root_proj = get_node(nodes, name)
      root_proj.is_root_proj = True
    if "MSB3277:" in line:
      line = trim_msberr_line(line)
      proj = parse_project_name(line)
      line = strip_proj_portion(line)
      if line.startswith(" Found conflicts between different versions of"):
        ref_num = 0
      elif line.startswith("     References which depend on"): # Conflict start
        ref_num += 1
        ref = None
        asm = parse_references_which_depend_on(line)
        version = asm.version
        conflict = get_node(nodes, asm.name)
        conflict.is_conflict = True
      elif conflict and conflict_dep_rx.search(line): # Conflict <- Dep1 start
        name = parse_assembly_name(line)
        ref = get_node(nodes, name)
        conflict.references.add(Ref(ref, version, ref_num == 1))
      elif ref and conflict_dep_dep_rx.search(line): # Conflict <- Dep1 <- Dep2 start
        name = parse_assembly_name(line)
        refref = get_node(nodes, name)
        ref.references.add(Ref(refref, version, ref_num == 1))
        refref.references.add(Ref(get_node(nodes, proj), version, ref_num == 1))
    else:
      conflict = ref = version = None
  for node in nodes:
    if node.references and node.name != root_proj.name:
      node.references.add(Ref(root_proj))
  return nodes

def create_graph_simple(nodes):
  g = GV.Digraph(
    filename="Diagram",
    directory=tempfile.gettempdir(),
    format="svg")
  combos = set()
  for node in nodes:
    for ref in node.references:
      a = ref.name
      b = node.name
      if a != b and ((a,b) not in combos or (b,a) not in combos):
        combos.add((a,b))
        combos.add((b,a))
        if node.is_conflict:
          g.node(b, style="filled", fillcolor="salmon")
        if ref.is_root_proj:
          g.node(a, style="filled", fillcolor="aquamarine")
        if ref.version:
          g.edge(a, b, label=ref.version, color="blue" if ref.is_primary else "black")
        else:
          g.edge(a, b)
  g.attr(overlap="false")
  g.attr(splines="true")
  g.view()

def run_msbuild(build_dir=""):
  return os.popen(f"msbuild /v:d {build_dir}").read()

if __name__ == "__main__":
  build_dir = sys.argv[-1]
  print(f"Building...")
  if os.path.isdir(build_dir):
    build_output = run_msbuild(build_dir)
  else:
    build_output = run_msbuild()
  print("Parsing results...")
  nodes = parse_build_output(build_output)
  print("Creating graph...")
  create_graph_simple(nodes)
  print("Done")
