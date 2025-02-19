# admin_app.py
import sys
import time
import tkinter as tk
from tkinter import simpledialog, messagebox, ttk
import os
from db.hajj_db import get_connection, init_db, get_hajj_records, create_hajj_record, update_hajj_record


class AdminAppGUI:
    def __init__(self, root, logger, admin_nfc, admin_fingerprint):
        self.root = root
        self.logger = logger
        self.admin_nfc = admin_nfc
        self.admin_fingerprint = admin_fingerprint
        self.logged_in_username = None

        # Configure root window
        self.root.title("Admin Login")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.minsize(300, 200)

        # Initialize styles
        self.create_styles()
        self._create_login_screen()

    def create_styles(self):
        """Define custom styles for the application."""
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Helvetica", 24, "bold"))
        style.configure("Normal.TLabel", font=("Helvetica", 12))
        style.configure("Warning.TLabel", font=("Helvetica", 12), foreground="red")
        style.configure("Success.TLabel", font=("Helvetica", 12), foreground="green")
        style.configure("Danger.TButton",
                        font=("Helvetica", 12, "bold"),
                        foreground="red")

    def _create_login_screen(self):
        """Create the initial login screen."""
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(expand=True)

        ttk.Label(frame, text="Login", style="Header.TLabel").pack(pady=(0, 20))

        credentials_frame = ttk.Frame(frame)
        credentials_frame.pack(fill="x")

        ttk.Label(credentials_frame, text="Username:").grid(row=0, column=0, padx=5, pady=5)
        ttk.Label(credentials_frame, text="Password:").grid(row=1, column=0, padx=5, pady=5)

        self.username_entry = ttk.Entry(credentials_frame)
        self.password_entry = ttk.Entry(credentials_frame, show="*")

        self.username_entry.grid(row=0, column=1, padx=5, pady=5)
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(frame, text="Login", command=self._handle_login).pack(pady=20)

    def _handle_login(self):
        """Handle login attempt and validation."""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if username == "ad" and password == "123":
            self.logged_in_username = username
            self.logger.log_admin(username, "Login", success=True)

            # Set logged_in_username for both admin handlers
            self.admin_nfc.logged_in_username = username
            self.admin_fingerprint.logged_in_username = username

            messagebox.showinfo("Success", "Login successful")
            self._open_admin_panel()
        else:
            self.logger.log_admin(username, "Login", success=False,
                                  message="Invalid credentials")
            messagebox.showerror("Error", "Invalid credentials")

    def _open_admin_panel(self):
        """Create and display the admin control panel."""
        # Clear current window
        for widget in self.root.winfo_children():
            widget.destroy()

        self.root.title(f"Admin Panel - {self.logged_in_username}")

        # Create main frame with padding
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(expand=True, fill="both")

        # Header
        ttk.Label(
            main_frame,
            text="Hajj Authentication System Admin",
            style="Header.TLabel"
        ).pack(pady=(0, 20))

        # Create grid frame
        grid_frame = ttk.Frame(main_frame)
        grid_frame.pack(expand=True)

        # Define admin actions with grid positions
        actions = [
            ("Add New Hajj", self._add_new_hajj, False, 0, 0),
            ("Write NFC", self._write_nfc, False, 0, 1),
            ("Read NFC", self._read_nfc, False, 0, 2),
            ("Assign Fingerprint", self._assign_fingerprint, False, 1, 0),
            ("Check Fingerprint", self._check_fingerprint, False, 1, 1),
            ("Display Database", self._display_db, False, 1, 2),
            ("Delete All Fingerprints", self._delete_all_fingerprints, True, 2, 0),
            ("Reset System", self._reset_system, True, 2, 1),
            ("Exit", self._exit_app, False, 2, 2)
        ]

        # Configure box button style
        style = ttk.Style()
        style.configure(
            "Box.TButton",
            padding=20,
            width=15,
            font=("Helvetica", 12)
        )
        style.configure(
            "BoxDanger.TButton",
            padding=20,
            width=15,
            font=("Helvetica", 12, "bold"),
            foreground="red"
        )

        # Create box-style buttons
        for text, command, is_dangerous, row, col in actions:
            btn = ttk.Button(
                grid_frame,
                text=text,
                command=command,
                style="BoxDanger.TButton" if is_dangerous else "Box.TButton"
            )
            btn.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

    def _write_nfc(self):
        """Write data to NFC card."""
        try:
            hajj_id = simpledialog.askstring("Write NFC", "Enter Hajj ID:")
            if not hajj_id:
                return

            if self.admin_nfc.write_nfc_data(hajj_id):
                messagebox.showinfo("Success", f"Wrote Hajj ID {hajj_id} to card")
            else:
                messagebox.showerror("Error", "Failed to write to NFC card")

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _read_nfc(self):
        """Read data from NFC card."""
        try:
            if messagebox.askyesno("Read NFC",
                                 "Read decrypted data? Select No for raw data."):
                data = self.admin_nfc.read_nfc_data()
                label = "Decrypted"
            else:
                data = self.admin_nfc.pn532_nfc.read_nfc(timeout=0.1)
                label = "Raw"

            if data:
                messagebox.showinfo("Success", f"{label} Data: {data}")
            else:
                messagebox.showwarning("Warning", "No data read")

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def get_next_available_location(self):
        """Find next available fingerprint location (1-120)."""
        try:
            hajj_records = get_hajj_records()
            used_locations = set()

            for record in hajj_records:
                if record.get('fingerprint_data') and record['fingerprint_data'].get('location'):
                    try:
                        location = int(record['fingerprint_data']['location'])
                        if 1 <= location <= 120:
                            used_locations.add(location)
                    except (ValueError, TypeError):
                        continue

            for location in range(1, 121):
                if location not in used_locations:
                    return location

            return None

        except Exception as e:
            self.logger.log_admin(
                self.logged_in_username,
                "GetNextLocation",
                success=False,
                message=str(e)
            )
            return None

    def _display_db(self):
        try:
            hajj_records = get_hajj_records()

            info = "=== Database Contents ===\n\n"
            for record in hajj_records:
                info += f"Hajj ID: {record['hajj_id']}\n"
                info += f"Name: {record['name']}\n"
                if record.get('nfc_data'):
                    info += f"NFC UID: {record['nfc_data'].get('uid', 'N/A')}\n"
                if record.get('fingerprint_data'):
                    info += f"Fingerprint Location: {record['fingerprint_data'].get('location', 'N/A')}\n"
                info += "-------------------\n"

            messagebox.showinfo("DB Contents", info)
        except Exception as e:
            messagebox.showerror("DB Error", f"Failed to fetch data: {str(e)}")

    def _reset_system(self):
        if not messagebox.askyesno("WARNING",
                                   "This will DELETE ALL DATA from the system!\nThis action CANNOT be undone!\nAre you absolutely sure?",
                                   icon='warning'):
            return

        try:
            # Clear database
            conn = get_connection()
            c = conn.cursor()
            c.execute("DROP TABLE IF EXISTS hajj_records")
            init_db()
            conn.close()

            # Clear fingerprint sensor
            for i in range(1, 121):
                try:
                    self.admin_fingerprint.fingerprint_manager.delete_model(i)
                except:
                    continue

            # Clear logs
            for log_dir in [os.path.join("logs", "admin"), os.path.join("logs", "user")]:
                if os.path.exists(log_dir):
                    for file in os.listdir(log_dir):
                        os.remove(os.path.join(log_dir, file))

            messagebox.showinfo("Success", "System has been reset to factory settings")

        except Exception as e:
            messagebox.showerror("Reset Failed", f"System reset failed: {str(e)}")

    def _assign_fingerprint(self):
        """Enhanced debug version of fingerprint assignment using SystemLogger"""
        hajj_id = simpledialog.askstring("Assign Fingerprint", "Enter Hajj ID:")
        if not hajj_id:
            return

        try:
            # Debug: Print available locations
            location = self.get_next_available_location()
            self.logger.log_admin(
                self.logged_in_username,
                "AssignFingerprint",
                True,
                f"Got next available location: {location}"
            )

            if location is None:
                raise Exception("No available fingerprint locations")

            if not messagebox.askyesno("Enroll Fingerprint", "Place finger on sensor for enrollment"):
                return

            self.logger.log_admin(
                self.logged_in_username,
                "AssignFingerprint",
                True,
                "Starting fingerprint enrollment process..."
            )

            success = self.admin_fingerprint.fingerprint_manager.enroll_finger(location)
            self.logger.log_admin(
                self.logged_in_username,
                "AssignFingerprint",
                success,
                f"Enrollment result: {success}"
            )

            if success:
                try:
                    self.logger.log_admin(
                        self.logged_in_username,
                        "AssignFingerprint",
                        True,
                        "Attempting to get fingerprint data..."
                    )

                    # Attempt 1: Try with raw buffer type
                    try:
                        raw_data = self.admin_fingerprint.fingerprint_manager.finger.get_fpdata('raw')
                        self.logger.log_admin(
                            self.logged_in_username,
                            "AssignFingerprint",
                            True,
                            f"Raw data retrieved, type: {type(raw_data)}, length: {len(raw_data) if raw_data else 'None'}"
                        )
                    except Exception as e:
                        self.logger.log_admin(
                            self.logged_in_username,
                            "AssignFingerprint",
                            False,
                            f"Error getting raw data: {str(e)}"
                        )
                        raw_data = None

                    # Attempt 2: Try with char buffer type
                    try:
                        template = self.admin_fingerprint.fingerprint_manager.finger.get_fpdata('char')
                        self.logger.log_admin(
                            self.logged_in_username,
                            "AssignFingerprint",
                            True,
                            f"Template data retrieved, type: {type(template)}, length: {len(template) if template else 'None'}"
                        )
                    except Exception as e:
                        self.logger.log_admin(
                            self.logged_in_username,
                            "AssignFingerprint",
                            False,
                            f"Error getting template data: {str(e)}"
                        )
                        template = None

                    # Attempt 3: Try without buffer type if both attempts fail
                    if raw_data is None:
                        try:
                            raw_data = self.admin_fingerprint.fingerprint_manager.finger.get_fpdata()
                            template = raw_data  # Use same data for both if this works
                            self.logger.log_admin(
                                self.logged_in_username,
                                "AssignFingerprint",
                                True,
                                f"Generic data retrieved, type: {type(raw_data)}, length: {len(raw_data) if raw_data else 'None'}"
                            )
                        except Exception as e:
                            self.logger.log_admin(
                                self.logged_in_username,
                                "AssignFingerprint",
                                False,
                                f"Error getting generic data: {str(e)}"
                            )
                            raise Exception("Could not retrieve fingerprint data in any format")

                    fingerprint_data = {
                        'location': str(location),
                        'template': template.hex() if isinstance(template, bytes) else bytes(
                            template).hex() if template else None,
                        'raw_image': raw_data.hex() if isinstance(raw_data, bytes) else bytes(
                            raw_data).hex() if raw_data else None,
                        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
                    }

                    self.logger.log_admin(
                        self.logged_in_username,
                        "AssignFingerprint",
                        True,
                        f"Fingerprint data prepared: {fingerprint_data}"
                    )

                    update_hajj_record(hajj_id, {'fingerprint_data': fingerprint_data})
                    messagebox.showinfo("Success", f"Fingerprint enrolled for {hajj_id} at location {location}")
                    self.logger.log_admin(
                        self.logged_in_username,
                        f"AssignFingerprint[{hajj_id}]",
                        True
                    )

                except Exception as inner_e:
                    self.logger.log_admin(
                        self.logged_in_username,
                        "AssignFingerprint",
                        False,
                        f"Error during fingerprint data processing: {str(inner_e)}"
                    )
                    # Try to clean up if data processing failed
                    try:
                        self.admin_fingerprint.fingerprint_manager.delete_model(location)
                        self.logger.log_admin(
                            self.logged_in_username,
                            "AssignFingerprint",
                            True,
                            f"Cleaned up fingerprint at location {location} after error"
                        )
                    except Exception as cleanup_e:
                        self.logger.log_admin(
                            self.logged_in_username,
                            "AssignFingerprint",
                            False,
                            f"Error during cleanup: {str(cleanup_e)}"
                        )
                    raise inner_e
            else:
                messagebox.showerror("Error", "Enrollment failed")

        except Exception as e:
            error_msg = f"Operation failed: {str(e)}"
            self.logger.log_admin(
                self.logged_in_username,
                f"AssignFingerprint[{hajj_id}]",
                False,
                error_msg
            )
            messagebox.showerror("Error", error_msg)

    def _delete_all_fingerprints(self):
        if not messagebox.askyesno("Warning", "This will delete ALL fingerprint data. Continue?"):
            return

        try:
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Deleting Fingerprints")
            progress_window.geometry("300x100")

            label = tk.Label(progress_window, text="Deleting fingerprints...")
            label.pack(pady=10)

            progress = tk.Label(progress_window, text="0/128")
            progress.pack(pady=5)

            def update_progress(i):
                progress.config(text=f"{i}/128")
                progress_window.update()

            # Delete from sensor and database
            hajj_records = get_hajj_records()
            for i in range(128):
                try:
                    self.admin_fingerprint.fingerprint_manager.delete_model(i)
                    # Update any records with this fingerprint location
                    for record in hajj_records:
                        if (record.get('fingerprint_data') and
                                record['fingerprint_data'].get('location') == str(i)):
                            update_hajj_record(record['hajj_id'], {'fingerprint_data': None})
                    update_progress(i + 1)
                except:
                    pass

            progress_window.destroy()
            messagebox.showinfo("Success", "All fingerprint data deleted")

        except Exception as e:
            messagebox.showerror("Error", f"Delete failed: {str(e)}")

    def _check_fingerprint(self):
        """Enhanced fingerprint checking with detailed debugging."""
        try:
            self.logger.log_admin(
                self.logged_in_username,
                "CheckFingerprint",
                True,
                "Starting fingerprint check..."
            )

            # Get fingerprint match from sensor
            found, finger_id, confidence = self.admin_fingerprint.fingerprint_manager.search_fingerprint()

            self.logger.log_admin(
                self.logged_in_username,
                "CheckFingerprint",
                True,
                f"Sensor result: found={found}, finger_id={finger_id}, confidence={confidence}"
            )

            if not found or finger_id is None:
                self.logger.log_admin(
                    self.logged_in_username,
                    "CheckFingerprint",
                    False,
                    "No fingerprint match found on sensor"
                )
                messagebox.showwarning("Not Found", "No matching fingerprint found")
                return

            # Get all records for debugging
            hajj_records = get_hajj_records()
            self.logger.log_admin(
                self.logged_in_username,
                "CheckFingerprint",
                True,
                f"Retrieved {len(hajj_records)} records from database"
            )

            # Search through records with detailed logging
            found_record = None
            for record in hajj_records:
                if record.get('fingerprint_data'):
                    stored_location = record['fingerprint_data'].get('location')
                    self.logger.log_admin(
                        self.logged_in_username,
                        "CheckFingerprint",
                        True,
                        f"Checking record: hajj_id={record['hajj_id']}, stored_location={stored_location}, comparing with finger_id={finger_id}"
                    )

                    if stored_location == str(finger_id):
                        found_record = record
                        break

            if found_record:
                self.logger.log_admin(
                    self.logged_in_username,
                    "CheckFingerprint",
                    True,
                    f"Found matching record: Hajj ID={found_record['hajj_id']}"
                )

                summary = (
                    f"Found matching record!\n\n"
                    f"Hajj ID: {found_record['hajj_id']}\n"
                    f"Name: {found_record['name']}\n"
                    f"Fingerprint Location: {found_record['fingerprint_data']['location']}\n"
                    f"Match Confidence: {confidence}"
                )
                messagebox.showinfo("Success", summary)
            else:
                self.logger.log_admin(
                    self.logged_in_username,
                    "CheckFingerprint",
                    False,
                    f"No database record found for finger_id={finger_id}"
                )
                messagebox.showwarning(
                    "Not Found",
                    f"Fingerprint matched on sensor (ID: {finger_id}, Confidence: {confidence})\n"
                    f"but no corresponding record found in database.\n\n"
                    f"This may indicate a synchronization issue."
                )

        except Exception as e:
            error_msg = f"Check failed: {str(e)}"
            self.logger.log_admin(
                self.logged_in_username,
                "CheckFingerprint",
                False,
                error_msg
            )
            messagebox.showerror("Error", error_msg)

    def _delete_fingerprint_location(self, location):
        """
        Delete a fingerprint from a specific location.

        :param location: The location number to clear
        :return: True if successful, False otherwise
        """
        try:
            if self.admin_fingerprint.fingerprint_manager.delete_model(location):
                # Update database to remove the fingerprint record
                # This would require adding a new function to hajj_db.py
                self.logger.info(f"Deleted fingerprint from location {location}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error deleting fingerprint at location {location}: {e}")
            return False

    def _cleanup_failed_enrollment(self, hajj_id, stage, location=None):
        """
        Clean up any partial records if enrollment fails midway.

        Args:
            hajj_id: The Hajj ID being enrolled
            stage: The stage at which the enrollment failed ('nfc', 'fingerprint', 'database')
            location: Optional fingerprint location to clean up
        """
        self.logger.log_admin(
            self.logged_in_username,
            f"Cleanup[{hajj_id}]",
            True,
            f"Starting cleanup for failed enrollment at stage: {stage}"
        )

        try:
            # Clean up database record
            conn = get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM hajj_records WHERE hajj_id = ?", (hajj_id,))
            conn.commit()
            conn.close()

            self.logger.log_admin(
                self.logged_in_username,
                f"Cleanup[{hajj_id}]",
                True,
                "Database record removed"
            )

            # Clean up fingerprint if enrolled
            if location is not None:
                try:
                    self.admin_fingerprint.fingerprint_manager.delete_model(location)
                    self.logger.log_admin(
                        self.logged_in_username,
                        f"Cleanup[{hajj_id}]",
                        True,
                        f"Fingerprint at location {location} removed"
                    )
                except Exception as fp_error:
                    self.logger.log_admin(
                        self.logged_in_username,
                        f"Cleanup[{hajj_id}]",
                        False,
                        f"Failed to clean up fingerprint: {str(fp_error)}"
                    )

            # For NFC cleanup, we can't "un-write" the card, but we can log it
            if stage == 'nfc':
                self.logger.log_admin(
                    self.logged_in_username,
                    f"Cleanup[{hajj_id}]",
                    True,
                    "Note: NFC card may need manual cleanup"
                )

        except Exception as e:
            self.logger.log_admin(
                self.logged_in_username,
                f"Cleanup[{hajj_id}]",
                False,
                f"Cleanup failed: {str(e)}"
            )
            raise Exception(f"Failed to clean up enrollment data: {str(e)}")

    def _add_new_hajj(self):
        """Complete workflow for adding a new Hajj record with enhanced error handling and validation."""

        # Stage 1: Input Validation
        try:
            # Get and validate Hajj ID
            hajj_id = simpledialog.askstring("New Hajj", "Enter Hajj ID:")
            if not hajj_id:
                self.logger.log_admin(self.logged_in_username, "AddHajj", False, "Cancelled at Hajj ID entry")
                return

            # Check if Hajj ID already exists
            existing_records = get_hajj_records()
            if any(record['hajj_id'] == hajj_id for record in existing_records):
                self.logger.log_admin(self.logged_in_username, "AddHajj", False, f"Hajj ID {hajj_id} already exists")
                messagebox.showerror("Error", "This Hajj ID already exists in the system")
                return

            # Get and validate name
            hajj_name = simpledialog.askstring("New Hajj", "Enter Hajj Name:")
            if not hajj_name:
                self.logger.log_admin(self.logged_in_username, "AddHajj", False, "Cancelled at name entry")
                return

            if len(hajj_name.strip()) < 2:
                self.logger.log_admin(self.logged_in_username, "AddHajj", False, "Invalid name length")
                messagebox.showerror("Error", "Name must be at least 2 characters long")
                return

            # Stage 2: Initial Record Creation
            record = {
                'hajj_id': hajj_id,
                'name': hajj_name.strip()
            }

            self.logger.log_admin(
                self.logged_in_username,
                f"AddHajj[{hajj_id}]",
                True,
                "Initial record created"
            )

            # Stage 3: NFC Card Registration
            if not messagebox.askyesno("NFC Registration",
                                       "Place NFC card on reader.\nMake sure only one card is present.\nContinue?"):
                self.logger.log_admin(self.logged_in_username, "AddHajj", False, "Cancelled at NFC stage")
                return

            # NFC Detection with timeout and retries
            max_retries = 3
            for attempt in range(max_retries):
                self.logger.log_admin(
                    self.logged_in_username,
                    f"AddHajj[{hajj_id}]",
                    True,
                    f"NFC detection attempt {attempt + 1}/{max_retries}"
                )

                uid = self.admin_nfc.pn532_nfc.wait_for_card(timeout=5)
                if uid:
                    break

                if attempt < max_retries - 1:
                    if not messagebox.askyesno("Retry", "No NFC card detected. Try again?"):
                        self.logger.log_admin(self.logged_in_username, "AddHajj", False, "User cancelled NFC retry")
                        return
                else:
                    raise Exception("No NFC card detected after maximum attempts")

            # Check if NFC card is already registered
            uid_str = '-'.join(hex(i)[2:] for i in uid)
            if any(record.get('nfc_data', {}).get('uid') == uid_str for record in existing_records):
                self.logger.log_admin(self.logged_in_username, "AddHajj", False,
                                      f"NFC card {uid_str} already registered")
                messagebox.showerror("Error", "This NFC card is already registered in the system")
                return

            # Write data to NFC card
            encrypted_data = self.admin_nfc.write_nfc_data(hajj_id)
            if not encrypted_data:
                raise Exception("Failed to write to NFC card - encryption error")

            # Add NFC data to record
            record['nfc_data'] = {
                'uid': uid_str,
                'encrypted_data': encrypted_data,
                'decrypted_data': hajj_id
            }

            # Stage 4: Save Initial Record
            new_record = create_hajj_record(record)
            if not new_record:
                raise Exception("Database error: Failed to create initial record")

            self.logger.log_admin(
                self.logged_in_username,
                f"AddHajj[{hajj_id}]",
                True,
                "NFC registration complete"
            )

            # Stage 5: Fingerprint Enrollment
            if not messagebox.askyesno("Fingerprint",
                                       "Ready to enroll fingerprint.\nPlace finger on the sensor when prompted.\nContinue?"):
                self.logger.log_admin(self.logged_in_username, "AddHajj", False, "Cancelled at fingerprint stage")
                return

            # Get next available fingerprint location
            location = self.get_next_available_location()
            if location is None:
                raise Exception("No available fingerprint locations (maximum capacity reached)")

            # Enroll fingerprint with detailed status
            self.logger.log_admin(
                self.logged_in_username,
                f"AddHajj[{hajj_id}]",
                True,
                f"Starting fingerprint enrollment at location {location}"
            )

            if not self.admin_fingerprint.fingerprint_manager.enroll_finger(location):
                raise Exception("Fingerprint enrollment failed - could not capture valid print")

            # Get fingerprint data with error handling
            try:
                template = self.admin_fingerprint.fingerprint_manager.finger.get_fpdata()
                raw_image = template  # Use same data if separate raw image not needed

                fingerprint_data = {
                    'location': str(location),
                    'template': template.hex() if isinstance(template, bytes) else bytes(template).hex(),
                    'raw_image': raw_image.hex() if isinstance(raw_image, bytes) else bytes(raw_image).hex(),
                    'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
                }

                # Update record with fingerprint data
                updated_record = update_hajj_record(hajj_id, {'fingerprint_data': fingerprint_data})
                if not updated_record:
                    raise Exception("Failed to update record with fingerprint data")

            except Exception as fp_error:
                # Clean up on fingerprint data error
                self.logger.log_admin(
                    self.logged_in_username,
                    f"AddHajj[{hajj_id}]",
                    False,
                    f"Error processing fingerprint data: {str(fp_error)}"
                )
                try:
                    self.admin_fingerprint.fingerprint_manager.delete_model(location)
                except:
                    pass
                raise Exception(f"Failed to process fingerprint data: {str(fp_error)}")

            # Stage 6: Final Success
            self.logger.log_admin(
                self.logged_in_username,
                f"AddHajj[{hajj_id}]",
                True,
                "Enrollment completed successfully"
            )

            # Show detailed success summary
            summary = (
                f"Enrollment Complete!\n\n"
                f"Hajj ID: {updated_record['hajj_id']}\n"
                f"Name: {updated_record['name']}\n"
                f"NFC UID: {updated_record['nfc_data'].get('uid', 'N/A')}\n"
                f"Fingerprint Location: {updated_record['fingerprint_data'].get('location', 'N/A')}\n\n"
                f"Timestamp: {fingerprint_data['timestamp']}"
            )
            messagebox.showinfo("Success", summary)

        except Exception as e:
            error_msg = str(e)
            self.logger.log_admin(
                self.logged_in_username,
                f"AddHajj[{hajj_id if 'hajj_id' in locals() else 'Unknown'}]",
                False,
                error_msg
            )

            # Show detailed error message
            detailed_error = (
                f"Enrollment failed\n\n"
                f"Error: {error_msg}\n\n"
                f"Please check the logs for more details and try again."
            )
            messagebox.showerror("Error", detailed_error)

            # Attempt to clean up any partial records
            try:
                if 'hajj_id' in locals() and 'new_record' in locals():
                    stage = 'database'
                    if 'location' in locals():
                        stage = 'fingerprint'
                    elif 'encrypted_data' in locals():
                        stage = 'nfc'

                    self._cleanup_failed_enrollment(
                        hajj_id,
                        stage,
                        location if 'location' in locals() else None
                    )
            except Exception as cleanup_error:
                self.logger.log_admin(
                    self.logged_in_username,
                    "AddHajj_Cleanup",
                    False,
                    f"Cleanup error: {str(cleanup_error)}"
                )
                messagebox.showwarning(
                    "Warning",
                    "Failed to clean up partial enrollment data.\nManual cleanup may be required."
                )

    def _on_closing(self):
        """Handle window close event."""
        if messagebox.askokcancel("Quit", "Do you want to exit?"):
            self._exit_app()

    def _exit_app(self):
        """Clean up and exit application."""
        try:
            # Close hardware connections
            if hasattr(self, 'admin_fingerprint'):
                self.admin_fingerprint.fingerprint_manager.uart.close()

            self.logger.log_admin(
                self.logged_in_username,
                "Logout",
                success=True
            )

            # Destroy window and exit
            self.root.destroy()
            sys.exit(0)

        except Exception as e:
            self.logger.log_admin(
                self.logged_in_username,
                "Logout",
                success=False,
                message=str(e)
            )
            sys.exit(1)