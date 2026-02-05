from modules.base import Module

class BuildToolsModule(Module):
    id = "build_tools"
    label = "Build Tools"
    description = "Essential compilation tools (gcc, make, base-devel/build-essential)"
    category = "Infrastructure"
    
    package_name = {
        "arch": "base-devel",
        "ubuntu": "build-essential"
    }
