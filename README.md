# msbuild-conflicts

Turns nasty [MSB3277](https://docs.microsoft.com/en-us/visualstudio/msbuild/errors/msb3277?view=vs-2022) build warnings like this:
```
There was a conflict between "System.Net.Http, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b03f5f7f11d50a3a" and "System.Net.Http, Version=4.2.0.0, Culture=neutral, PublicKeyToken=b03f5f7f11d50a3a".
    "System.Net.Http, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b03f5f7f11d50a3a" was chosen because it was primary and "System.Net.Http, Version=4.2.0.0, Culture=neutral, PublicKeyToken=b03f5f7f11d50a3a" was not.
    References which depend on "System.Net.Http, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b03f5f7f11d50a3a" [C:\Program Files (x86)\Reference Assemblies\Microsoft\Framework\.NETFramework\v4.6.1\System.Net.Http.dll].
        C:\Program Files (x86)\Reference Assemblies\Microsoft\Framework\.NETFramework\v4.6.1\System.Net.Http.dll
          Project file item includes which caused reference "C:\Program Files (x86)\Reference Assemblies\Microsoft\Framework\.NETFramework\v4.6.1\System.Net.Http.dll".
            System.Net.Http
    References which depend on "System.Net.Http, Version=4.2.0.0, Culture=neutral, PublicKeyToken=b03f5f7f11d50a3a" [C:\src\projects\BrightMetricsWeb\RingCentral\RingCentralRepository\bin\Debug\System.Net.Http.dll].
        C:\src\projects\BrightMetricsWeb\RingCentral\RingCentralRepository\bin\Debug\netstandard.dll
          Project file item includes which caused reference "C:\src\projects\BrightMetricsWeb\RingCentral\RingCentralRepository\bin\Debug\netstandard.dll".
            C:\src\projects\BrightMetricsWeb\RingCentral\RingCentralRepository\bin\Debug\RingCentralRepository.dll
        C:\src\projects\BrightMetricsWeb\RingCentral\RingCentralRepository\bin\Debug\Azure.Core.dll
          Project file item includes which caused reference "C:\src\projects\BrightMetricsWeb\RingCentral\RingCentralRepository\bin\Debug\Azure.Core.dll".
            C:\src\projects\BrightMetricsWeb\RingCentral\RingCentralRepository\bin\Debug\RingCentralRepository.dll
        C:\src\projects\BrightMetricsWeb\RingCentral\RingCentralRepository\bin\Debug\System.Net.Http.Formatting.dll
          Project file item includes which caused reference "C:\src\projects\BrightMetricsWeb\RingCentral\RingCentralRepository\bin\Debug\System.Net.Http.Formatting.dll".
            C:\src\projects\BrightMetricsWeb\RingCentral\RingCentralRepository\bin\Debug\RingCentralRepository.dll			
```

into a pretty diagram:

![image](https://user-images.githubusercontent.com/8726792/186281382-421f2d7a-bf4d-4ab0-925c-fbf3d8a538a6.png)

## Prerequisites

(For Windows only)

1. You need to install Python, which typically the Windows installer ensures the `py` command is globally available. If not, you'll need to make sure it is.
1. Powershell
1. You'll need to download [GraphViz](https://www.graphviz.org/download/) and after the install make sure that the `/bin` directory is added to your PATH environment variable (the official 3rd party Python library requires it).
1. Make sure that MSBuild's `/bin` directory is added to your PATH environment variable.
1. Download this repository. `cd` into it and run `py -m pip install -r .` That will install the third party libraries used in this repo.
1. Add the `src` directory of this repository to your PATH environment variable.

That's it! Easy as py.

## Usage

Open up a powershell prompt and `cd` into whatever .NET project directory you want. If your build is showing MSB3277 warnings, you can run `conflicts.ps1` from that directory and it'll run this program, finishing by opening up whatever program you have configured to view SVGs in.

The **blue arrows** mean that is the reference that _won_ the conflict (the primary reference). The **red nodes** are the dependencies that are experiencing conflicts. The **green node** is the project that you ran MSBuild on.
