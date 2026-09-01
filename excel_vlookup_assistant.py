import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd

class ExcelVLookupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Excel VLOOKUP Assistant")
        self.root.geometry("900x720")
        self.root.minsize(800, 650)

        self.source_file = ""
        self.target_file = ""
        self.source_sheets = {}
        self.target_sheets = {}

        self.build_ui()

    def build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        title = ttk.Label(
            self.root,
            text="Excel VLOOKUP Assistant",
            font=("Segoe UI", 22, "bold")
        )
        title.pack(pady=(20, 5))

        subtitle = ttk.Label(
            self.root,
            text="Compare IDs between two Excel files and copy selected data",
            font=("Segoe UI", 10)
        )
        subtitle.pack(pady=(0, 15))

        main = ttk.Frame(self.root, padding=20)
        main.pack(fill="both", expand=True)

        # Files
        files_frame = ttk.LabelFrame(main, text="1. Select Excel Files", padding=15)
        files_frame.pack(fill="x", pady=8)

        ttk.Label(files_frame, text="Source Excel (data to copy):").grid(
            row=0, column=0, sticky="w", pady=7
        )
        self.source_label = ttk.Label(files_frame, text="No file selected", width=65)
        self.source_label.grid(row=0, column=1, sticky="w", padx=10)
        ttk.Button(files_frame, text="Browse", command=self.select_source).grid(
            row=0, column=2
        )

        ttk.Label(files_frame, text="Target Excel (data to update):").grid(
            row=1, column=0, sticky="w", pady=7
        )
        self.target_label = ttk.Label(files_frame, text="No file selected", width=65)
        self.target_label.grid(row=1, column=1, sticky="w", padx=10)
        ttk.Button(files_frame, text="Browse", command=self.select_target).grid(
            row=1, column=2
        )

        # Sheets
        sheet_frame = ttk.LabelFrame(main, text="2. Select Sheets", padding=15)
        sheet_frame.pack(fill="x", pady=8)

        ttk.Label(sheet_frame, text="Source Sheet:").grid(row=0, column=0, sticky="w")
        self.source_sheet = ttk.Combobox(sheet_frame, state="readonly", width=35)
        self.source_sheet.grid(row=0, column=1, padx=10, pady=5)
        self.source_sheet.bind("<<ComboboxSelected>>", self.load_source_columns)

        ttk.Label(sheet_frame, text="Target Sheet:").grid(row=0, column=2, sticky="w")
        self.target_sheet = ttk.Combobox(sheet_frame, state="readonly", width=35)
        self.target_sheet.grid(row=0, column=3, padx=10, pady=5)
        self.target_sheet.bind("<<ComboboxSelected>>", self.load_target_columns)

        # ID columns
        id_frame = ttk.LabelFrame(main, text="3. Choose ID Columns", padding=15)
        id_frame.pack(fill="x", pady=8)

        ttk.Label(id_frame, text="Source ID Column:").grid(
            row=0, column=0, sticky="w", pady=6
        )
        self.source_id = ttk.Combobox(id_frame, state="readonly", width=35)
        self.source_id.grid(row=0, column=1, padx=10)

        ttk.Label(id_frame, text="Target ID Column:").grid(
            row=0, column=2, sticky="w", pady=6
        )
        self.target_id = ttk.Combobox(id_frame, state="readonly", width=35)
        self.target_id.grid(row=0, column=3, padx=10)

        # Columns to copy
        copy_frame = ttk.LabelFrame(
            main,
            text="4. Select Columns to Copy from Source",
            padding=15
        )
        copy_frame.pack(fill="both", expand=True, pady=8)

        list_area = ttk.Frame(copy_frame)
        list_area.pack(fill="both", expand=True)

        self.column_list = tk.Listbox(
            list_area,
            selectmode=tk.MULTIPLE,
            height=8,
            font=("Segoe UI", 10)
        )
        self.column_list.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(
            list_area,
            orient="vertical",
            command=self.column_list.yview
        )
        scroll.pack(side="right", fill="y")
        self.column_list.config(yscrollcommand=scroll.set)

        btns = ttk.Frame(copy_frame)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="Select All", command=self.select_all).pack(
            side="left", padx=4
        )
        ttk.Button(btns, text="Clear Selection", command=self.clear_selection).pack(
            side="left", padx=4
        )

        # Output
        output_frame = ttk.LabelFrame(main, text="5. Output", padding=15)
        output_frame.pack(fill="x", pady=8)

        self.output_label = ttk.Label(
            output_frame,
            text="Output will be created next to the target file",
            width=90
        )
        self.output_label.pack(anchor="w")

        ttk.Button(
            output_frame,
            text="Choose Output File",
            command=self.choose_output
        ).pack(anchor="w", pady=(8, 0))

        # Run
        self.run_button = ttk.Button(
            main,
            text="RUN VLOOKUP",
            command=self.run_vlookup
        )
        self.run_button.pack(pady=12, ipadx=35, ipady=8)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(
            main,
            textvariable=self.status_var,
            font=("Segoe UI", 10, "bold")
        ).pack(pady=3)

    def select_source(self):
        path = filedialog.askopenfilename(
            title="Select Source Excel",
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("All files", "*.*")
            ]
        )
        if not path:
            return

        try:
            self.source_file = path
            self.source_label.config(text=os.path.basename(path))

            self.source_sheets = pd.read_excel(path, sheet_name=None)
            sheets = list(self.source_sheets.keys())
            self.source_sheet["values"] = sheets

            if sheets:
                self.source_sheet.current(0)
                self.load_source_columns()

            self.status_var.set("Source Excel loaded.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not read source Excel:\n\n{e}")

    def select_target(self):
        path = filedialog.askopenfilename(
            title="Select Target Excel",
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("All files", "*.*")
            ]
        )
        if not path:
            return

        try:
            self.target_file = path
            self.target_label.config(text=os.path.basename(path))

            self.target_sheets = pd.read_excel(path, sheet_name=None)
            sheets = list(self.target_sheets.keys())
            self.target_sheet["values"] = sheets

            if sheets:
                self.target_sheet.current(0)
                self.load_target_columns()

            self.status_var.set("Target Excel loaded.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not read target Excel:\n\n{e}")

    def clean_columns(self, df):
        # Make duplicate/blank column names safe for selection.
        columns = []
        seen = {}
        for i, col in enumerate(df.columns):
            name = str(col).strip()
            if not name or name.lower() == "nan":
                name = f"Unnamed_{i+1}"
            if name in seen:
                seen[name] += 1
                name = f"{name}_{seen[name]}"
            else:
                seen[name] = 0
            columns.append(name)
        df.columns = columns
        return df

    def load_source_columns(self, event=None):
        if not self.source_sheets or not self.source_sheet.get():
            return

        df = self.clean_columns(
            self.source_sheets[self.source_sheet.get()].copy()
        )
        self.source_sheets[self.source_sheet.get()] = df

        cols = list(df.columns)
        self.source_id["values"] = cols

        self.column_list.delete(0, tk.END)
        for col in cols:
            self.column_list.insert(tk.END, col)

        if cols:
            self.source_id.current(0)

    def load_target_columns(self, event=None):
        if not self.target_sheets or not self.target_sheet.get():
            return

        df = self.clean_columns(
            self.target_sheets[self.target_sheet.get()].copy()
        )
        self.target_sheets[self.target_sheet.get()] = df

        cols = list(df.columns)
        self.target_id["values"] = cols

        if cols:
            self.target_id.current(0)

    def select_all(self):
        self.column_list.select_set(0, tk.END)

    def clear_selection(self):
        self.column_list.selection_clear(0, tk.END)

    def choose_output(self):
        path = filedialog.asksaveasfilename(
            title="Save Output Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )
        if path:
            self.output_path = path
            self.output_label.config(text=path)

    def normalize_id(self, value):
        if pd.isna(value):
            return ""
        # Prevent Excel numeric IDs such as 1001.0 from mismatching "1001".
        if isinstance(value, float) and value.is_integer():
            return str(int(value)).strip()
        return str(value).strip()

    def run_vlookup(self):
        if not self.source_file or not self.target_file:
            messagebox.showwarning(
                "Missing Files",
                "Please select both Source and Target Excel files."
            )
            return

        if not self.source_sheet.get() or not self.target_sheet.get():
            messagebox.showwarning(
                "Missing Sheet",
                "Please select both source and target sheets."
            )
            return

        source_id = self.source_id.get()
        target_id = self.target_id.get()

        if not source_id or not target_id:
            messagebox.showwarning(
                "Missing ID",
                "Please select the ID column in both files."
            )
            return

        selected = self.column_list.curselection()
        copy_cols = [self.column_list.get(i) for i in selected]

        if not copy_cols:
            messagebox.showwarning(
                "No Columns",
                "Please select at least one source column to copy."
            )
            return

        if source_id in copy_cols:
            copy_cols.remove(source_id)

        if not copy_cols:
            messagebox.showwarning(
                "Invalid Selection",
                "Please select columns other than the source ID column."
            )
            return

        try:
            self.status_var.set("Processing...")
            self.root.update_idletasks()

            source_df = self.clean_columns(
                self.source_sheets[self.source_sheet.get()].copy()
            )
            target_df = self.clean_columns(
                self.target_sheets[self.target_sheet.get()].copy()
            )

            # Normalize IDs for matching while preserving original data.
            source_keys = source_df[source_id].map(self.normalize_id)
            target_keys = target_df[target_id].map(self.normalize_id)

            # First occurrence wins, similar to VLOOKUP's first match behavior.
            lookup_df = source_df.loc[:, [source_id] + copy_cols].copy()
            lookup_df["_VLOOKUP_KEY_"] = source_keys
            lookup_df = lookup_df.drop_duplicates(
                subset="_VLOOKUP_KEY_",
                keep="first"
            )

            lookup_df = lookup_df.set_index("_VLOOKUP_KEY_")

            # Add/replace selected columns in target.
            for col in copy_cols:
                mapping = lookup_df[col].to_dict()
                target_df[col] = target_keys.map(mapping)

            matched_mask = target_keys.isin(
                set(lookup_df.index) - {""}
            )
            matched = int(matched_mask.sum())
            unmatched = int(len(target_df) - matched)

            # Default output path.
            if not hasattr(self, "output_path"):
                base, _ = os.path.splitext(self.target_file)
                self.output_path = base + "_VLOOKUP_Result.xlsx"

            # Write all target workbook sheets, replacing only selected target sheet.
            with pd.ExcelWriter(self.output_path, engine="openpyxl") as writer:
                for sheet_name, df in self.target_sheets.items():
                    if sheet_name == self.target_sheet.get():
                        target_df.to_excel(
                            writer,
                            sheet_name=sheet_name,
                            index=False
                        )
                    else:
                        df.to_excel(
                            writer,
                            sheet_name=sheet_name,
                            index=False
                        )

            self.output_label.config(text=self.output_path)
            self.status_var.set(
                f"Completed | Matched: {matched} | Unmatched: {unmatched}"
            )

            messagebox.showinfo(
                "VLOOKUP Complete",
                f"Processing completed successfully.\n\n"
                f"Matched IDs: {matched}\n"
                f"Unmatched IDs: {unmatched}\n"
                f"Columns copied: {len(copy_cols)}\n\n"
                f"Output:\n{self.output_path}"
            )

        except PermissionError:
            messagebox.showerror(
                "File Locked",
                "The output Excel file may be open in Excel. "
                "Close it and run again."
            )
        except Exception as e:
            self.status_var.set("Error")
            messagebox.showerror(
                "VLOOKUP Error",
                f"Something went wrong:\n\n{e}"
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = ExcelVLookupApp(root)
    root.mainloop()
