from modules.base import Module

class GdiskModule(Module):
    id = "gdisk"
    label = "GPT fdisk (gdisk)"
    description = "Text-mode partitioning tool for GPT disks, required by rEFInd"
    category = "Infrastructure"
    
    manager = "system"
    package_name = "gdisk"
    
    dependencies = {
        "arch": [],
        "ubuntu": []
    }
