# 🚀 Dotfiles Manager TUI

![Welcome Screen](./assets/welcome_screen.png)

Una herramienta interactiva y moderna para gestionar tus configuraciones de sistema (dotfiles) con elegancia, modularidad y una interfaz visual basada en la terminal (TUI). 🎨

## ✨ Interfaz

El gestor está dividido en pantallas intuitivas diseñadas para que no tengas que editar archivos de configuración manualmente:

### 1. 🏠 Pantalla de Bienvenida

Es tu centro de mando. Desde aquí puedes saltar directamente a la instalación de tus paquetes configurados o entrar al asistente para crear nuevos módulos desde cero.

### 2. 📦 Selector de Paquetes

Un menú organizado por categorías (Sistema, Terminal, Editores, etc.).

* **Selección Inteligente**: El sistema detecta automáticamente si un paquete necesita a otro (dependencias) y lo marca por ti.
* **Personalización**: Presionando `TAB` puedes entrar a las **Opciones del Paquete** para cambiar el nombre del paquete, el gestor (brew, cargo, system) o la ruta de destino.

### 3. 🧙 Wizard de Creación (Asistente)

Si tienes una nueva configuración, el Wizard te guía paso a paso.

* **Validación en tiempo real**: Te avisa si el ID ya existe o si falta algún dato.
* **Previsualización**: Verás cómo se genera el código Python de tu módulo mientras escribes.
* **Borradores**: Puedes guardar tu progreso y retomarlo después.

### 4. ⚙️ Instalador

Una vez confirmada tu selección, verás una barra de progreso detallada que te informa exactamente qué se está instalando y qué archivos se están vinculando en tu sistema.

---

## 🛠️ Instalación y Uso

### Requisitos

* **Python 3.10** o superior. 🐍

### Pasos para empezar

1. **Clonar el repositorio**:

    ```bash
    git clone https://github.com/iamseb4s/dotfiles.git
    cd dotfiles
    ```

2. **Lanzar el gestor**:

    **🐧 Linux / 🍎 macOS**:

    ```bash
    ./install.sh
    ```

    **🪟 Windows**:
    > *Próximamente.* Por ahora, se recomienda el uso de **WSL2**.

---

## ⌨️ Controles Básicos

| Tecla | Acción |
| :--- | :--- |
| `h / j / k / l` | Navegación (estilo Vim) |
| `ENTER` | Confirmar / Siguiente |
| `TAB` | Abrir opciones del paquete |
| `SPACE` | Seleccionar / Activar |
| `Q` | Volver / Salir |

---
*Basado en el esquema de colores [Catppuccin Macchiato](https://github.com/catppuccin/catppuccin).* 🐈
