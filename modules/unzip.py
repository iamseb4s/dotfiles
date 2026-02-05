from modules.base import Module

class UnzipModule(Module):
    id = "unzip"
    label = "Unzip"
    description = "Extraction utility for .zip archives"
    category = "Infrastructure"
    
    package_name = {
        "arch": "unzip",
        "ubuntu": "unzip"
    }
