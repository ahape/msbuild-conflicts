import re, os, sys, tempfile
import graphviz as GV

ref_which_dep_rx = re.compile(r'References which depend on "(.*?)"')
conflict_dep_rx = re.compile(r"^         \S")
conflict_dep_dep_rx = re.compile(r"^             \S")
dll_rx = re.compile(r"\\([^\\]+)\.(?:exe|dll)")
csproj_rx = re.compile(r"\\([^\\]+)\.csproj")

class Node():
  def __init__(self, name, is_conflict=None):
    self.id = id(name)
    self.name = name
    self.is_conflict = is_conflict
    self.is_root_proj = False
    self.references = set()
  def add_reference(self, ref):
    if ref.node.id == self.id:
      return False
    self.references.add(ref)
    return True
  def __repr__(self):
    return f"<Node {self.name}>"

class Ref():
  def __init__(self, node, version, is_primary):
    self.node = node
    self.version = version
    self.is_primary = is_primary
  def __hash__(self):
    return self.node.id
  def __eq__(self, other):
    return self.node.id == other.node.id
  def __repr__(self):
    return f"<Ref {self.node.name}>"

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
  root_proj, conflict, dep, version = None, None, None, None
  for line in build_output.splitlines():
    if not root_proj and line.startswith("Project "):
      name = csproj_rx.search(line)[1]
      root_proj = get_node(nodes, name)
      root_proj.is_root_proj = True
    if "MSB3277:" in line:
      line = trim_msberr_line(line)
      proj = parse_project_name(line)
      line = strip_proj_portion(line)
      is_prim = ref_num == 1
      if line.startswith(" Found conflicts between different versions of"):
        ref_num = 0
      elif line.startswith("     References which depend on"): # Conflict start
        ref_num += 1
        dep = None
        asm = parse_references_which_depend_on(line)
        version = asm.version
        conflict = get_node(nodes, asm.name)
        conflict.is_conflict = True
      elif conflict and conflict_dep_rx.search(line): # Conflict <- Dep1 start
        name = parse_assembly_name(line)
        dep = get_node(nodes, name)
        conflict.add_reference(Ref(dep, version, is_prim))
      elif dep and conflict_dep_dep_rx.search(line): # Conflict <- Dep1 <- Dep2 start
        name = parse_assembly_name(line)
        depdep = get_node(nodes, name)
        ver = version if depdep.is_conflict else None
        dep.add_reference(Ref(depdep, ver, is_prim))
        depdep.add_reference(Ref(get_node(nodes, proj), ver, is_prim))
    else:
      conflict = ref = version = None
  for node in nodes:
    if node.references and node.name != root_proj.name:
      node.add_reference(Ref(root_proj, None, False))
  """
  for node in nodes:
    print(node)
    for ref in node.references:
      print("\t", ref)
  """
  return nodes

def create_graph_simple(nodes):
  g = GV.Digraph(
    filename="Diagram",
    directory=tempfile.gettempdir(),
    format="svg")
  linkages = set()
  for node in nodes:
    for ref in node.references:
      r, n = ref.node.name, node.name
      linkage = "<->".join(sorted([r, n]))
      if r != n and linkage not in linkages:
        linkages.add(linkage)
        if node.is_conflict:
          g.node(n, style="filled", fillcolor="salmon")
        if ref.node.is_root_proj:
          g.node(r, style="filled", fillcolor="aquamarine")
        if ref.version:
          g.edge(r, n, label=ref.version, color="blue" if ref.is_primary else "black")
        else:
          g.edge(r, n)
  g.attr(overlap="false")
  g.attr(splines="true")
  g.view()

def run_msbuild(proj_file):
  return os.popen(f"msbuild {proj_file}").read()

def find_csproj(build_dir):
  for file in os.listdir(build_dir):
    if file.endswith(".csproj"):
      return file
  raise Exception("No .csproj file found")

if __name__ == "__main__":
  if len(sys.argv) == 1:
    raise Exception("Must pass in project directory path as argument")
  build_dir = sys.argv[-1]
  print(f"Building...")
  if build_dir.endswith(".txt"):
    build_output = open(build_dir).read()
  elif os.path.isdir(build_dir):
    build_output = run_msbuild(find_csproj(build_dir))
  else:
    raise Exception(f"Bad argument {build_dir}")

  print("Parsing results...")
  nodes = parse_build_output(build_output)
  print("Creating graph...")
  create_graph_simple(nodes)
  print("Done")
