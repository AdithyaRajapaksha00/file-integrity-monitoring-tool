import tkinter as tk
from tkinter import ttk, filedialog
from tkinterdnd2 import DND_FILES, TkinterDnD
import os

def get_all_files_in_directory(directory):
    """Recursively fetch all files inside a directory."""
    all_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            all_files.append(os.path.join(root, file))
    return all_files

def select_files_with_tkinter():
    """Opens a modern-looking Tkinter UI for selecting files or folders with drag-and-drop."""
    selected_files = []
    selected_folders = []

    def add_path_to_list(path):
        if os.path.isdir(path):
            if path not in selected_folders:
                selected_folders.append(path)
                file_list.insert(tk.END, f"[Folder] {path}")
                for file_path in get_all_files_in_directory(path):
                    if file_path not in selected_files:
                        selected_files.append(file_path)
                        file_list.insert(tk.END, file_path)
        else:
            if path not in selected_files:
                selected_files.append(path)
                file_list.insert(tk.END, path)

    def select_items():
        paths = filedialog.askopenfilenames()
        for path in paths:
            add_path_to_list(path)

    def select_folder():
        folder_path = filedialog.askdirectory()
        if folder_path:
            add_path_to_list(folder_path)

    def drop(event):
        paths = root.tk.splitlist(event.data)
        for path in paths:
            add_path_to_list(path)

    def confirm_selection():
        root.confirmed = True
        root.quit()
        root.destroy()

    root = TkinterDnD.Tk()
    root.title("Select Files or Folders")
    root.geometry("600x450")
    root.attributes('-topmost', True)

    # Apply a modern theme
    ttk.Style(root).theme_use('clam')  # Try other themes like 'vista', 'xpnative', 'alt'

    instruction = ttk.Label(root, text="Drag & Drop files/folders here or use the buttons below:", font=("Arial", 11))
    instruction.pack(pady=(10, 5), padx=10, fill='x')

    file_list_frame = ttk.Frame(root)
    file_list_frame.pack(pady=5, padx=10, fill='both', expand=True)
    file_list_scrollbar = ttk.Scrollbar(file_list_frame)
    file_list = tk.Listbox(file_list_frame, width=70, height=15, yscrollcommand=file_list_scrollbar.set)
    file_list_scrollbar.config(command=file_list.yview)
    file_list_scrollbar.pack(side='right', fill='y')
    file_list.pack(side='left', fill='both', expand=True)

    button_frame = ttk.Frame(root)
    button_frame.pack(pady=10, padx=10, fill='x')

    select_btn = ttk.Button(button_frame, text="Select Files", command=select_items)
    select_btn.pack(side='left', padx=(0, 5), fill='x', expand=True)

    folder_btn = ttk.Button(button_frame, text="Select Folder", command=select_folder)
    folder_btn.pack(side='left', padx=(5, 0), fill='x', expand=True)

    confirm_btn = ttk.Button(root, text="Confirm Selection", command=confirm_selection)
    confirm_btn.pack(pady=15, padx=10, fill='x')

    root.drop_target_register(DND_FILES)
    root.dnd_bind("<<Drop>>", drop)

    root.confirmed = False
    root.mainloop()

    return (selected_files, selected_folders) if root.confirmed else ([], [])