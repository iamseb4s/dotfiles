from modules.base import Module

class BtopModule(Module):
    id = "btop"
    label = "Btop"
    description = "Resource monitor that shows usage and stats for processor, memory, disks, network and processes"
    category = "Tools"
    
    package_name = {
        "arch": "btop",
        "ubuntu": "btop"
    }
