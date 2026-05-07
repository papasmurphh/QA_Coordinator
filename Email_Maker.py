import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, Toplevel, font
import json
import datetime
import os

# --- FIX: Create an absolute path to the templates file ---
# This ensures the program can find the JSON file regardless of how it's launched.
script_dir = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_FILE = os.path.join(script_dir, "meeting_email_templates.json")
# --- END FIX ---

# NEW: minimize the Windows console at startup; no effect on other OSes
def minimize_console_window():
    """Minimize the attached console window on Windows; safe no-op elsewhere."""
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            SW_MINIMIZE = 6
            user32.ShowWindow(hwnd, SW_MINIMIZE)
    except Exception:
        # Fail quietly if anything goes wrong
        pass
# --- END NEW ---

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

# Default templates (will be saved to JSON if file doesn't exist)
DEFAULT_TEMPLATES = {
    "QA Packaging": {
        "Pre": {
            "subject": "-MONTH- QA & Packaging Leadership Meeting Agenda",
            "body": "Attached is the agenda for our upcoming -MONTH- meeting between the Quality Assurance and Packaging teams. This meeting is designed to align our strategies, share key information, and foster collaboration in pursuit of our common goals. To ensure that our discussion is productive, please review the agenda topics in advance and come prepared to offer your insights or pose any questions.\nIf you have any suggestions for modifications or additional topics, kindly email me so that the agenda can be updated accordingly."
        },
        "Post": {
            "subject": "Agenda & Notes from the -MONTH- Meeting between Quality Assurance and Packaging Leadership",
            "body": "Attached is the -MONTH- agenda from our most recent Quality Assurance and Packaging Leadership meeting.\nBelow are the meeting notes.\nThank you all for your continued support and participation."
        }
    },
    "QA Manufacturing": {
        "Pre": {
            "subject": "-MONTH- QA & Manufacturing Leadership Meeting Agenda",
            "body": "Attached is the agenda for our upcoming -MONTH- meeting between the Quality Assurance and Manufacturing teams. This meeting is designed to align our strategies, share key information, and foster collaboration in pursuit of our common goals. To ensure that our discussion is productive, please review the agenda topics in advance and come prepared to offer your insights or pose any questions.\nIf you have any suggestions for modifications or additional topics, kindly email me so that the agenda can be updated accordingly."
        },
        "Post": {
            "subject": "Agenda & Notes from the -MONTH- Meeting between Quality Assurance and Manufacturing Leadership",
            "body": "Attached is the -MONTH- agenda from our most recent Quality Assurance and Manufacturing Leadership meeting.\nBelow are the meeting notes.\nThank you all for your continued support and participation."
        }
    },
    "QA Mason": {
        "Pre": {
            "subject": "-MONTH- QA & Mason Leadership Meeting Agenda",
            "body": "Attached is the agenda for our upcoming -MONTH- meeting between the Quality Assurance and Mason teams. This meeting is designed to align our strategies, share key information, and foster collaboration in pursuit of our common goals. To ensure that our discussion is productive, please review the agenda topics in advance and come prepared to offer your insights or pose any questions.\nIf you have any suggestions for modifications or additional topics, kindly email me so that the agenda can be updated accordingly."
        },
        "Post": {
            "subject": "Agenda & Notes from the -MONTH- Meeting between Quality Assurance and Mason Leadership",
            "body": "Attached is the -MONTH- agenda from our most recent Quality Assurance and Mason Leadership meeting.\nBelow are the meeting notes.\nThank you all for your continued support and participation."
        }
    },
    "Mason Bulk CAPA Meeting": {
        "Pre": {
            "subject": "-MONTH- Mason Bulk CAPA Meeting Agenda",
            "body": "Hi Team\nHope everyone is doing well. Please find below the link to the agenda for our upcoming -MONTH- Mason Bulk Defect CAPA meeting. During this session, we will review the -PREVIOUS MONTH- Hold Data, discuss the starch moisture specification adjustment, and address two open CAPAs [Air Bubbles and Syrup Leak in the DSK].\nIf you have any updates or additional topics to include, please inform me, and I will ensure the agenda is updated accordingly.\n\n--LINK HERE--\n\nThe monthly Mason Bulk Defect CAPA Meeting brings together leadership from Mason production, Product Development, Process Development and Quality Assurance to collaboratively address and manage Corrective and Preventive Actions related specifically to gummy bulk defects."
        }
        # No Post meeting for Mason Bulk CAPA by default
    },
    "QA Warehouse": {
        "Pre": {
            "subject": "-MONTH- QA & Warehouse Leadership Meeting Agenda",
            "body": "Attached is the agenda for our upcoming -MONTH- meeting between the Quality Assurance and Warehouse teams. This meeting is designed to align our strategies, share key information, and foster collaboration in pursuit of our common goals. To ensure that our discussion is productive, please review the agenda topics in advance and come prepared to offer your insights or pose any questions.\nIf you have any suggestions for modifications or additional topics, kindly email me so that the agenda can be updated accordingly."
        },
        "Post": {
            "subject": "Agenda & Notes from the -MONTH- Meeting between Quality Assurance and Warehouse Leadership",
            "body": "Attached is the -MONTH- agenda from our most recent Quality Assurance and Warehouse Leadership meeting.\nBelow are the meeting notes.\nThank you all for your continued support and participation."
        },
        "Stars & Wins Request": {
            "subject": "-MONTH- QA and Warehouse Meeting Stars and Wins",
            "body": "Hello Team,\nWith the -MONTH- QA and Warehouse bi-monthly Meeting coming up, I'd like your help nominating Warehouse individuals or groups during the last two months for our Quality Win and/or Quality Star Awards.\nPlease send me your nomination(s) for either or both awards, and I can make sure to recognize the person or team during our next meeting. Your input is vital in ensuring that our colleagues' efforts and accomplishments are acknowledged and celebrated, and also sets the meeting off to a great start! \nFor any questions or assistance, feel free to contact me."
        }
    }
}


class EmailCreatorApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Meeting Email Creator")
        self.root.geometry("850x750")

        self.templates_data = self.load_templates()
        self.current_meeting_name = tk.StringVar()
        self.current_email_type = tk.StringVar()

        # --- Style ---
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            # Theme may not be available on all systems
            pass
        
        # Default font
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(size=10, family="Segoe UI")
        self.root.option_add("*Font", default_font)
        
        # Configure styles for a more modern and polished look
        style.configure("TButton", padding=6, font=('Segoe UI', 10))
        style.configure("TLabel", padding=5, font=('Segoe UI', 10))
        style.configure("TEntry", padding=5)
        style.configure("TCombobox", padding=5)
        style.configure("TRadiobutton", padding=(10, 5), font=('Segoe UI', 10))
        style.configure("TLabelframe", padding=10)
        style.configure("TLabelframe.Label", font=('Segoe UI', 11, 'bold'), padding=(0, 5, 0, 5))

        # --- Main PanedWindow for resizable sections ---
        main_paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Left Pane: Controls ---
        controls_frame = ttk.Frame(main_paned_window, padding=10)
        main_paned_window.add(controls_frame, weight=2)

        # Date Selection
        date_frame = ttk.LabelFrame(controls_frame, text="Date Selection", padding=10)
        date_frame.pack(fill=tk.X, pady=5)

        ttk.Label(date_frame, text="Month:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.month_var = tk.StringVar(value=MONTHS[datetime.date.today().month - 1])
        self.month_combo = ttk.Combobox(date_frame, textvariable=self.month_var, values=MONTHS, state="readonly", width=15)
        self.month_combo.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)

        ttk.Label(date_frame, text="Year:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.year_var = tk.StringVar(value=str(datetime.date.today().year))
        self.year_entry = ttk.Entry(date_frame, textvariable=self.year_var, width=10)
        self.year_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        date_frame.columnconfigure(1, weight=1)

        # Meeting Selection
        meeting_frame = ttk.LabelFrame(controls_frame, text="Meeting Configuration", padding=10)
        meeting_frame.pack(fill=tk.X, pady=10)

        ttk.Label(meeting_frame, text="Meeting Type:").pack(anchor=tk.W, padx=5)
        self.meeting_type_combo = ttk.Combobox(meeting_frame, textvariable=self.current_meeting_name,
                                               values=list(self.templates_data.keys()), state="readonly")
        self.meeting_type_combo.pack(fill=tk.X, padx=5, pady=5)
        self.meeting_type_combo.bind("<<ComboboxSelected>>", self.on_meeting_selected)

        # Email Type Selection (Dynamic)
        ttk.Label(meeting_frame, text="Email Type:").pack(anchor=tk.W, padx=5, pady=(10,0))
        self.email_type_frame = ttk.Frame(meeting_frame)  # Frame to hold radio buttons
        self.email_type_frame.pack(fill=tk.X, padx=5, pady=5)
        self.email_type_radios = []

        # Action Buttons
        action_buttons_frame = ttk.Frame(controls_frame, padding=10)
        action_buttons_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)

        self.generate_button = ttk.Button(action_buttons_frame, text="Generate Email", command=self.generate_email_content)
        self.generate_button.pack(fill=tk.X, pady=4)

        self.save_template_button = ttk.Button(action_buttons_frame, text="Save Changes to This Template", command=self.save_current_template)
        self.save_template_button.pack(fill=tk.X, pady=4)
        
        self.create_new_button = ttk.Button(action_buttons_frame, text="Create/Add New Template", command=self.open_create_template_dialog)
        self.create_new_button.pack(fill=tk.X, pady=4)

        # --- Right Pane: Email Output ---
        output_frame_container = ttk.Frame(main_paned_window, padding=10)
        main_paned_window.add(output_frame_container, weight=3)  # Give more weight to output

        output_frame = ttk.LabelFrame(output_frame_container, text="Email Output", padding=10)
        output_frame.pack(fill=tk.BOTH, expand=True)

        # Subject
        ttk.Label(output_frame, text="Subject:").pack(anchor=tk.W, pady=(0, 2))
        self.subject_entry = ttk.Entry(output_frame, width=60, font=("Segoe UI", 10))
        self.subject_entry.pack(fill=tk.X, expand=True, pady=(0, 10))

        # Body
        ttk.Label(output_frame, text="Body:").pack(anchor=tk.W, pady=(5, 2))
        self.body_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=15, width=70, relief=tk.SUNKEN, borderwidth=1, font=("Segoe UI", 10))
        self.body_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # --- Copy Buttons Frame ---
        copy_buttons_frame = ttk.Frame(output_frame)
        copy_buttons_frame.pack(fill=tk.X, pady=(10, 0))
        copy_buttons_frame.columnconfigure((0, 1), weight=1)

        self.copy_title_button = ttk.Button(copy_buttons_frame, text="Copy Title", command=self.copy_title)
        self.copy_title_button.grid(row=0, column=0, sticky=tk.EW, padx=(0, 5))

        self.copy_body_button = ttk.Button(copy_buttons_frame, text="Copy Body", command=self.copy_body)
        self.copy_body_button.grid(row=0, column=1, sticky=tk.EW, padx=(5, 0))

        # --- Status Bar ---
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Initialize
        if list(self.templates_data.keys()):
            self.current_meeting_name.set(list(self.templates_data.keys())[0])
            self.on_meeting_selected(None)  # Populate email types for the first meeting

    def update_status(self, message, duration=3000):
        self.status_var.set(message)
        if duration:
            self.root.after(duration, lambda: self.status_var.set(""))

    def load_templates(self):
        if os.path.exists(TEMPLATES_FILE):
            try:
                with open(TEMPLATES_FILE, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                messagebox.showerror("Error", f"Could not decode {TEMPLATES_FILE}. Using default templates.")
                self.save_templates(DEFAULT_TEMPLATES)  # Save defaults if file is corrupt
                return DEFAULT_TEMPLATES.copy()  # Return a copy
            except Exception as e:
                messagebox.showerror("Error", f"Error loading {TEMPLATES_FILE}: {e}. Using default templates.")
                self.save_templates(DEFAULT_TEMPLATES)
                return DEFAULT_TEMPLATES.copy()
        else:
            self.save_templates(DEFAULT_TEMPLATES)
            return DEFAULT_TEMPLATES.copy()

    def save_templates(self, data):
        try:
            with open(TEMPLATES_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            self.update_status("Templates saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save templates to {TEMPLATES_FILE}: {e}")
            self.update_status(f"Error saving templates: {e}")

    def on_meeting_selected(self, event):
        selected_meeting = self.current_meeting_name.get()
        self.clear_output_fields()

        # Clear previous radio buttons
        for radio in self.email_type_radios:
            radio.destroy()
        self.email_type_radios.clear()
        self.current_email_type.set("")  # Clear selection

        if selected_meeting in self.templates_data:
            available_types = list(self.templates_data[selected_meeting].keys())
            if available_types:
                for type_name in available_types:
                    rb = ttk.Radiobutton(self.email_type_frame, text=type_name,
                                         variable=self.current_email_type, value=type_name,
                                         command=self.clear_output_fields_on_type_change)  # Clear on type change
                    rb.pack(anchor='w', fill='x', pady=2)
                    self.email_type_radios.append(rb)
                self.current_email_type.set(available_types[0])  # Select first one by default
            else:
                self.update_status(f"No email types defined for {selected_meeting}.")
        else:
            self.update_status(f"Meeting '{selected_meeting}' not found in templates.")
            
    def clear_output_fields_on_type_change(self):
        self.clear_output_fields()

    def clear_output_fields(self):
        self.subject_entry.delete(0, tk.END)
        self.body_text.delete('1.0', tk.END)

    def get_previous_month(self, current_month_str):
        try:
            current_month_index = MONTHS.index(current_month_str)
            previous_month_index = (current_month_index - 1 + 12) % 12  # +12 handles January gracefully
            return MONTHS[previous_month_index]
        except ValueError:
            return "[INVALID MONTH]"

    def generate_email_content(self):
        self.clear_output_fields()
        month = self.month_var.get()
        try:
            year = int(self.year_var.get())  # Basic validation
            if not (1900 < year < 2100):
                messagebox.showwarning("Input Error", "Please enter a valid year (e.g., 2023).")
                return
        except ValueError:
            messagebox.showwarning("Input Error", "Year must be a number.")
            return

        meeting = self.current_meeting_name.get()
        email_type = self.current_email_type.get()

        if not all([month, year, meeting, email_type]):
            messagebox.showwarning("Input Error", "Please select month, year, meeting, and email type.")
            return

        try:
            template = self.templates_data[meeting][email_type]
            subject_template = template['subject']
            body_template = template['body']

            # Replace placeholders
            final_subject = subject_template.replace("-MONTH-", month)
            final_body = body_template.replace("-MONTH-", month)

            if "-PREVIOUS MONTH-" in final_body:
                prev_month = self.get_previous_month(month)
                final_body = final_body.replace("-PREVIOUS MONTH-", prev_month)
            
            if "-PREVIOUS MONTH-" in final_subject:
                prev_month = self.get_previous_month(month)
                final_subject = final_subject.replace("-PREVIOUS MONTH-", prev_month)

            self.subject_entry.insert(0, final_subject)
            self.body_text.insert('1.0', final_body)
            self.update_status("Email content generated.")

        except KeyError:
            messagebox.showerror("Template Error", f"Template not found for {meeting} - {email_type}.")
            self.update_status(f"Template error for {meeting} - {email_type}.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")
            self.update_status(f"Error: {e}")

    def copy_to_clipboard(self, content, item_name):
        if not content.strip():
            self.update_status(f"{item_name} is empty. Nothing copied.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.update_status(f"{item_name} copied to clipboard.")

    def copy_title(self):
        self.copy_to_clipboard(self.subject_entry.get(), "Title")

    def copy_body(self):
        self.copy_to_clipboard(self.body_text.get('1.0', tk.END).strip(), "Body")

    # NEW: normalize month names back into placeholder tokens before saving
    def normalize_placeholders_for_save(self, text: str) -> str:
        """
        Converts the currently selected month name and its previous month
        back into -MONTH- and -PREVIOUS MONTH- so templates stay reusable.
        """
        month = self.month_var.get()
        if month:
            # Replace current month with -MONTH-
            text = text.replace(month, "-MONTH-")

            # Replace previous month with -PREVIOUS MONTH-
            prev_month = self.get_previous_month(month)
            if prev_month != "[INVALID MONTH]":
                text = text.replace(prev_month, "-PREVIOUS MONTH-")

        return text

    def save_current_template(self):
        meeting_name = self.current_meeting_name.get()
        email_type = self.current_email_type.get()
        new_subject = self.subject_entry.get()
        new_body = self.body_text.get('1.0', tk.END).strip()

        if not all([meeting_name, email_type]):
            messagebox.showwarning("Selection Error", "Please select a meeting and email type first.")
            return

        if not new_subject and not new_body:
            if not messagebox.askyesno("Confirm Save", "Subject and Body are empty. Save empty template?"):
                return
        
        confirm = messagebox.askyesno(
            "Confirm Save",
            f"Are you sure you want to overwrite the template for\n'{meeting_name}' - '{email_type}'?"
        )
        if confirm:
            try:
                # Normalize any literal month names back to placeholders
                new_subject_norm = self.normalize_placeholders_for_save(new_subject)
                new_body_norm = self.normalize_placeholders_for_save(new_body)

                if meeting_name not in self.templates_data:
                    self.templates_data[meeting_name] = {}
                if email_type not in self.templates_data[meeting_name]:
                    self.templates_data[meeting_name][email_type] = {}
                
                self.templates_data[meeting_name][email_type]['subject'] = new_subject_norm
                self.templates_data[meeting_name][email_type]['body'] = new_body_norm
                self.save_templates(self.templates_data)
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save template: {e}")
                self.update_status(f"Error saving template: {e}")

    def open_create_template_dialog(self):
        dialog = Toplevel(self.root)
        dialog.title("Create/Add New Email Template")
        dialog.geometry("500x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Meeting Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        meeting_name_entry = ttk.Entry(main_frame, width=40)
        meeting_name_entry.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)
        ttk.Label(main_frame, text="(Enter new name or select existing)").grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(main_frame, text="Email Type Name:").grid(row=2, column=0, sticky=tk.W, pady=5)
        email_type_entry = ttk.Entry(main_frame, width=40)
        email_type_entry.grid(row=2, column=1, sticky=tk.EW, pady=5, padx=5)
        ttk.Label(main_frame, text="(e.g., Pre, Post, Follow-up)").grid(row=3, column=1, sticky=tk.W, padx=5)

        ttk.Label(main_frame, text="Subject Template:").grid(row=4, column=0, sticky=tk.NW, pady=5)
        subject_template_entry = ttk.Entry(main_frame, width=40)
        subject_template_entry.grid(row=4, column=1, sticky=tk.EW, pady=5, padx=5)
        ttk.Label(main_frame, text="Use -MONTH- and -PREVIOUS MONTH-").grid(row=5, column=1, sticky=tk.W, padx=5)

        ttk.Label(main_frame, text="Body Template:").grid(row=6, column=0, sticky=tk.NW, pady=5)
        body_template_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=8, width=40)
        body_template_text.grid(row=6, column=1, sticky=tk.NSEW, pady=5, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(6, weight=1)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=10, sticky=tk.E)

        def do_save_new_template():
            m_name = meeting_name_entry.get().strip()
            e_type = email_type_entry.get().strip()
            s_tpl = subject_template_entry.get()
            b_tpl = body_template_text.get('1.0', tk.END).strip()

            if not m_name or not e_type:
                messagebox.showerror("Input Error", "Meeting Name and Email Type Name are required.", parent=dialog)
                return

            if m_name not in self.templates_data:
                self.templates_data[m_name] = {}
            
            self.templates_data[m_name][e_type] = {
                "subject": s_tpl,
                "body": b_tpl
            }
            self.save_templates(self.templates_data)
            self.refresh_meeting_list_combobox()
            
            if self.current_meeting_name.get() == m_name:
                self.on_meeting_selected(None)
            elif m_name not in self.meeting_type_combo['values']:
                self.current_meeting_name.set(m_name)
                self.on_meeting_selected(None)

            self.update_status(f"Template '{m_name} - {e_type}' saved.")
            dialog.destroy()

        save_btn = ttk.Button(button_frame, text="Save New Template", command=do_save_new_template)
        save_btn.pack(side=tk.LEFT, padx=5)
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=dialog.destroy)
        cancel_btn.pack(side=tk.LEFT, padx=5)

        current_selected_meeting = self.current_meeting_name.get()
        if current_selected_meeting:
            meeting_name_entry.insert(0, current_selected_meeting)
        
        dialog.wait_window()

    def refresh_meeting_list_combobox(self):
        current_selection = self.current_meeting_name.get()
        new_meeting_list = sorted(list(self.templates_data.keys()))
        self.meeting_type_combo['values'] = new_meeting_list
        if current_selection in new_meeting_list:
            self.current_meeting_name.set(current_selection)
        elif new_meeting_list:
            self.current_meeting_name.set(new_meeting_list[0])
            self.on_meeting_selected(None)
        else:
            self.current_meeting_name.set("")
            self.on_meeting_selected(None)


if __name__ == '__main__':
    # Minimize console before creating the GUI
    minimize_console_window()

    main_root = tk.Tk()

    # Optional: nudge the window to front in case the console steals focus briefly
    try:
        main_root.after(150, lambda: (main_root.lift(),
                                      main_root.attributes("-topmost", True),
                                      main_root.after(150, lambda: main_root.attributes("-topmost", False))))
    except Exception:
        pass

    app = EmailCreatorApp(main_root)
    main_root.mainloop()