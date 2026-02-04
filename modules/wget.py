from modules.base import Module

class WgetModule(Module):
    id = "wget"
    label = "Wget"
    description = "Tool for retrieving files using HTTP, HTTPS, and FTP"
    category = "Infrastructure"
    
    package_name = {
        "arch": "wget",
        "ubuntu": "wget"
    }
