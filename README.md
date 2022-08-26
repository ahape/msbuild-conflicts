# msbuild-conflicts

Turns nasty [MSB3277](https://docs.microsoft.com/en-us/visualstudio/msbuild/errors/msb3277?view=vs-2022) build warnings like this:
```
warning MSB3277: Found conflicts between different versions of "SharedDependency" that could not be resolved. [C:\Users\Me\source\repos\ExampleProgram\ExampleProgram.csproj]
warning MSB3277: There was a conflict between "SharedDependency, Version=1.0.0.0, Culture=neutral, PublicKeyToken=3e1fed751cb61585" and "SharedDependency, Version=1.0.0.1, Culture=neutral, PublicKeyToken=3e1fed751cb61585". [C:\Users\Me\source\repos\ExampleProgram\ExampleProgram.csproj]
warning MSB3277:     "SharedDependency, Version=1.0.0.0, Culture=neutral, PublicKeyToken=3e1fed751cb61585" was chosen because it was primary and "SharedDependency, Version=1.0.0.1, Culture=neutral, PublicKeyToken=3e1fed751cb61585" was not. [C:\Users\Me\source\repos\ExampleProgram\ExampleProgram.csproj]
warning MSB3277:     References which depend on "SharedDependency, Version=1.0.0.0, Culture=neutral, PublicKeyToken=3e1fed751cb61585" [C:\Users\Me\source\repos\SharedDependency\Versions\1.0.0.0\SharedDependency.dll]. [C:\Users\Me\source\repos\ExampleProgram\ExampleProgram.csproj]
warning MSB3277:         C:\Users\Me\source\repos\SharedDependency\Versions\1.0.0.0\SharedDependency.dll [C:\Users\Me\source\repos\ExampleProgram\ExampleProgram.csproj]
warning MSB3277:           Project file item includes which caused reference "C:\Users\Me\source\repos\SharedDependency\Versions\1.0.0.0\SharedDependency.dll". [C:\Users\Me\source\repos\ExampleProgram\ExampleProgram.csproj]
warning MSB3277:             SharedDependency, Version=1.0.0.0, Culture=neutral, PublicKeyToken=3e1fed751cb61585 [C:\Users\Me\source\repos\ExampleProgram\ExampleProgram.csproj]
warning MSB3277:     References which depend on "SharedDependency, Version=1.0.0.1, Culture=neutral, PublicKeyToken=3e1fed751cb61585" [C:\Users\Me\source\repos\LibraryB\bin\Debug\SharedDependency.dll]. [C:\Users\Me\source\repos\ExampleProgram\ExampleProgram.csproj]
warning MSB3277:         C:\Users\Me\source\repos\LibraryA\bin\Debug\LibraryA.dll [C:\Users\Me\source\repos\ExampleProgram\ExampleProgram.csproj]
warning MSB3277:           Project file item includes which caused reference "C:\Users\Me\source\repos\LibraryA\bin\Debug\LibraryA.dll". [C:\Users\Me\source\repos\ExampleProgram\ExampleProgram.csproj]
warning MSB3277:             LibraryA [C:\Users\Me\source\repos\ExampleProgram\ExampleProgram.csproj]
warning MSB3277:         C:\Users\Me\source\repos\LibraryB\bin\Debug\LibraryB.dll [C:\Users\Me\source\repos\ExampleProgram\ExampleProgram.csproj]
warning MSB3277:           Project file item includes which caused reference "C:\Users\Me\source\repos\LibraryB\bin\Debug\LibraryB.dll". [C:\Users\Me\source\repos\ExampleProgram\ExampleProgram.csproj]
warning MSB3277:             LibraryB [C:\Users\Me\source\repos\ExampleProgram\ExampleProgram.csproj]			
```

into a pretty diagram:

![image](https://user-images.githubusercontent.com/8726792/186794177-0cd378b1-8014-41be-a6c8-a4019916bc3e.png)

## Prerequisites

(For Windows only)

1. You need to install Python (latest version will work fine), which typically the Windows installer ensures the `py` command is globally available. If not, you'll need to make sure it is.
1. Powershell
1. You'll need to download [GraphViz](https://www.graphviz.org/download/) (latest version should work fine) and after the install make sure that the `/bin` directory is added to your PATH environment variable (the official 3rd party Python library requires it).
1. Make sure that MSBuild's `/bin` directory is added to your PATH environment variable. You can typically find that somewhere like this: `c:\Program Files (x86)\Microsoft Visual Studio\<Year>\<Product>\MSBuild\Current\Bin`.
1. Clone this repository. Fire up a terminal and `cd` into your locally cloned repo and then run the snippet below. That will install the (open source) third party libraries used in this repo.
```
py -m pip install -r requirements.txt
```
6. Add the `/src` directory of this repository to your PATH environment variable.

That's it! Easy as py. Nyuck nyuck nyuck.

## Usage

Open up a powershell prompt and `cd` into whatever .NET project directory you want. If your build is showing MSB3277 warnings, you can run `conflicts.ps1` from that directory and it'll run this program, finishing by opening up whatever program you have configured to view SVGs in.

The **blue arrows** mean that is the reference that _won_ the conflict (the primary reference). The **red nodes** are the dependencies that are experiencing conflicts. The **green node** is the project that you ran MSBuild on.
