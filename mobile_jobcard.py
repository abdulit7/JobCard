import os
os.environ["FLET_SECRET_KEY"] = "mysecret123"
import flet as ft
import sqlite3
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import time
import asyncio
from flet_audio import Audio
import uuid
import re

class JobCardPage(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.page.title = "Job Card Management"
        self.page.window.title = "Job Card Management"
        self.page.window.maximized = False
        self.page.window.resizable = True
        self.page.window.width = 400
        self.page.window.height = 700
        self.expand = True
        self.padding = ft.padding.all(6)
        self.bgcolor = ft.Colors.BLUE_GREY_50
        self.job_cards = []
        self.departments = []
        self.selected_status = None
        self.sqlite_db_path = "job_cards.db"
        self.device_id = str(uuid.uuid4())[-4:]  # Last 4 digits of UUID for device-specific job numbers
        self.is_syncing = False  # Lock for sync/upload operations

        # Initialize snackbar
        self.snack_bar = ft.SnackBar(
            content=ft.Text("", size=8, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            bgcolor=ft.Colors.BLACK,
            duration=6000,
            show_close_icon=True,
            behavior=ft.SnackBarBehavior.FLOATING,
            width=340,
            padding=10,
            margin=ft.margin.only(bottom=10),
            shape=ft.RoundedRectangleBorder(radius=8)
        )
        self.page.overlay.append(self.snack_bar)

        self.init_sqlite_db()

        self.add_job_card_button = ft.ElevatedButton(
            text="New Job",
            icon=ft.Icons.ADD_CIRCLE,
            bgcolor=ft.Colors.TEAL_600,
            color=ft.Colors.WHITE,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                overlay_color=ft.Colors.TEAL_800
            ),
            width=100,
            height=45,
            on_click=self.open_job_card_dialog
        )

        # self.sync_button = ft.ElevatedButton(
        #     text="Sync",
        #     icon=ft.Icons.SYNC,
        #     bgcolor=ft.Colors.TEAL_600,
        #     color=ft.Colors.WHITE,
        #     style=ft.ButtonStyle(
        #         shape=ft.RoundedRectangleBorder(radius=10),
        #         overlay_color=ft.Colors.TEAL_800
        #     ),
        #     width=100,
        #     height=45,
        #     on_click=self.sync_from_mysql
        # )

        # self.upload_button = ft.ElevatedButton(
        #     text="Upload",
        #     icon=ft.Icons.CLOUD_UPLOAD,
        #     bgcolor=ft.Colors.TEAL_600,
        #     color=ft.Colors.WHITE,
        #     style=ft.ButtonStyle(
        #         shape=ft.RoundedRectangleBorder(radius=10),
        #         overlay_color=ft.Colors.TEAL_800
        #     ),
        #     width=100,
        #     height=45,
        #     on_click=self.upload_to_mysql
        # )

        self.status_filter = ft.Dropdown(
            label="Status",
            options=[
                ft.dropdown.Option(key=None, text="All"),
                ft.dropdown.Option("Open"),
                ft.dropdown.Option("Started"),
                ft.dropdown.Option("Completed")
            ],
            value=None,
            on_change=self.filter_job_cards,
            border_color=ft.Colors.BLUE_300,
            color=ft.Colors.BLUE_900,
            text_size=8,
            width=140,
            dense=True
        )

        self.job_card_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Job No", size=8, weight=ft.FontWeight.BOLD, width=80)),
                ft.DataColumn(ft.Text("Title", size=8, weight=ft.FontWeight.BOLD, width=200)),
                ft.DataColumn(ft.Text("Status", size=8, weight=ft.FontWeight.BOLD, width=80)),
                ft.DataColumn(ft.Text("Actions", size=8, weight=ft.FontWeight.BOLD, width=60))
            ],
            rows=[],
            column_spacing=5,
            heading_row_height=25,
            data_row_min_height=18,
            data_row_max_height=34,
            border=ft.border.all(1, ft.Colors.BLUE_GREY_200),
            bgcolor=ft.Colors.WHITE,
            visible=True
        )

        self.load_departments()
        self.load_job_cards()

        self.content = ft.Column(
            controls=[
                ft.Divider(height=20, color=ft.Colors.BLUE_GREY_300),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text("Job Cards", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                icon_color=ft.Colors.WHITE,
                                tooltip="Refresh",
                                on_click=lambda e: self.load_job_cards()
                            ),
                            ft.IconButton(
                                icon=ft.Icons.UPLOAD_FILE,
                                icon_color=ft.Colors.WHITE,
                                tooltip="Upload",
                                on_click=self.upload_to_mysql
                            ),
                            ft.IconButton(
                                icon=ft.Icons.SYNC,
                                icon_color=ft.Colors.WHITE,
                                tooltip="Sync",
                                on_click=self.sync_from_mysql
                            )
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    bgcolor=ft.Colors.BLUE_800,
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    border_radius=8,
                    border=ft.border.all(1, ft.Colors.BLUE_GREY_400),
                    height=50
                ),
                ft.Row(
                    controls=[self.status_filter, self.add_job_card_button],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=5
                ),
                ft.Container(
                    content=ft.ListView(
                        controls=[
                            ft.Row(
                                controls=[self.job_card_table],
                                scroll=ft.ScrollMode.AUTO
                            )
                        ],
                        expand=True,
                        spacing=0,
                        padding=0
                    ),
                    width=390,
                    height=620,
                    border=ft.border.all(1, ft.Colors.BLUE_GREY_300),
                    border_radius=8,
                    padding=ft.padding.all(4),
                    bgcolor=ft.Colors.WHITE,
                    visible=True
                )
            ],
            expand=True,
            spacing=5,
            scroll=ft.ScrollMode.AUTO
        )

    def init_sqlite_db(self):
        conn = None
        cursor = None
        try:
            conn = sqlite3.connect(self.sqlite_db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS job_cards (
                    id INTEGER PRIMARY KEY,
                    job_number TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_date TEXT NOT NULL,
                    started_date TEXT,
                    completed_date TEXT,
                    entity_type TEXT,
                    entity_id INTEGER,
                    closure_details TEXT,
                    department_name TEXT NOT NULL
                )
            ''')
            conn.commit()
        except sqlite3.Error as e:
            self.show_snack_bar(f"Error initializing database: {e}", ft.Colors.RED_800)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def load_departments(self):
        db_config = {
            "host": "200.200.200.23",
            "user": "root",
            "password": "Pak@123",
            "database": "asm_sys"
        }
        conn = None
        cursor = None
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, name FROM department")
            self.departments = cursor.fetchall()
        except Error as e:
            self.show_snack_bar(f"Error fetching departments: {e}", ft.Colors.RED_800)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def safe_update(self, context=""):
        try:
            time.sleep(0.2)  # Increased delay for Android stability
            if hasattr(self.page, 'update_async'):
                asyncio.run_coroutine_threadsafe(self.page.update_async(), asyncio.get_event_loop())
            else:
                self.page.update()
        except Exception as e:
            self.show_snack_bar(f"UI update failed: {e}", ft.Colors.RED_800)

    def load_job_cards(self):
        self.job_cards = []
        conn = None
        cursor = None
        try:
            conn = sqlite3.connect(self.sqlite_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM job_cards WHERE 1=1"
            params = []
            if self.selected_status:
                query += " AND status = ?"
                params.append(self.selected_status)
            cursor.execute(query, params)
            self.job_cards = [dict(row) for row in cursor.fetchall()]
            for jc in self.job_cards:
                if jc['entity_type'] and jc['entity_id']:
                    jc['entity_info'] = self.get_entity_info(jc['entity_type'], jc['entity_id'])
                else:
                    jc['entity_info'] = "No entity assigned"
            self.job_card_table.rows = self.create_job_card_table()
            self.safe_update("load_job_cards")
        except (sqlite3.Error, Exception) as e:
            self.show_snack_bar(f"Error loading job cards: {e}", ft.Colors.RED_800)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def sync_from_mysql(self, e):
        if self.is_syncing:
            self.show_snack_bar("Sync in progress, please wait.", ft.Colors.YELLOW_800)
            return
        self.is_syncing = True
        self.sync_button.disabled = True
        self.upload_button.disabled = True
        self.safe_update("disable_sync_buttons")
        db_config = {
            "host": "200.200.200.23",
            "user": "root",
            "password": "Pak@123",
            "database": "asm_sys"
        }
        conn_sqlite = None
        conn_mysql = None
        cursor_sqlite = None
        cursor_mysql = None
        try:
            # Connect to MySQL
            conn_mysql = mysql.connector.connect(**db_config)
            cursor_mysql = conn_mysql.cursor(dictionary=True)
            # Connect to SQLite
            conn_sqlite = sqlite3.connect(self.sqlite_db_path)
            cursor_sqlite = conn_sqlite.cursor()
            # Fetch all job cards from MySQL
            cursor_mysql.execute("""
                SELECT id, job_number, title, description, status, created_date, started_date,
                       completed_date, entity_type, entity_id, closure_details, department_name
                FROM job_cards
            """)
            mysql_job_cards = cursor_mysql.fetchall()
            # Insert or update job cards in SQLite
            for jc in mysql_job_cards:
                try:
                    values = (
                        jc['id'],
                        jc['job_number'],
                        jc['title'],
                        jc['description'],
                        jc['status'],
                        jc['created_date'].strftime('%Y-%m-%d %H:%M:%S') if jc['created_date'] else None,
                        jc['started_date'].strftime('%Y-%m-%d %H:%M:%S') if jc['started_date'] else None,
                        jc['completed_date'].strftime('%Y-%m-%d %H:%M:%S') if jc['completed_date'] else None,
                        jc['entity_type'],
                        jc['entity_id'],
                        jc['closure_details'],
                        jc['department_name']
                    )
                    # Check if job card exists in SQLite
                    cursor_sqlite.execute("SELECT id FROM job_cards WHERE id = ?", (jc['id'],))
                    if cursor_sqlite.fetchone():
                        # Update existing job card
                        cursor_sqlite.execute("""
                            UPDATE job_cards
                            SET job_number = ?, title = ?, description = ?, status = ?, created_date = ?,
                                started_date = ?, completed_date = ?, entity_type = ?, entity_id = ?,
                                closure_details = ?, department_name = ?
                            WHERE id = ?
                        """, values[1:] + (jc['id'],))
                    else:
                        # Insert new job card
                        cursor_sqlite.execute("""
                            INSERT INTO job_cards (id, job_number, title, description, status, created_date,
                                                  started_date, completed_date, entity_type, entity_id,
                                                  closure_details, department_name)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, values)
                    conn_sqlite.commit()
                except sqlite3.Error as e:
                    self.show_snack_bar(f"Error syncing job card {jc['job_number']} to SQLite: {e}", ft.Colors.RED_800)
                    continue
            self.show_snack_bar("Job cards downloaded successfully!", ft.Colors.TEAL_600)
            self.load_job_cards()
            try:
                self.page.add(Audio(src="https://www.soundjay.com/buttons/beep-01a.mp3", autoplay=True))
                if hasattr(self.page, 'top_bar_ref') and self.page.top_bar_ref.current:
                    self.page.top_bar_ref.current.update_notification_icon()
            except Exception as e:
                self.show_snack_bar(f"Error playing audio: {e}", ft.Colors.RED_800)
        except Error as e:
            if e.errno == 2003:
                self.show_snack_bar("Sync failed: Cannot connect to database server", ft.Colors.RED_800)
            else:
                self.show_snack_bar(f"Sync failed: Database error - {e}", ft.Colors.RED_800)
        except Exception as e:
            self.show_snack_bar(f"Sync failed: {e}", ft.Colors.RED_800)
        finally:
            if cursor_sqlite:
                cursor_sqlite.close()
            if conn_sqlite:
                conn_sqlite.close()
            if cursor_mysql:
                cursor_mysql.close()
            if conn_mysql:
                conn_mysql.close()
            self.is_syncing = False
            self.sync_button.disabled = False
            self.upload_button.disabled = False
            self.safe_update("enable_sync_buttons")

    def upload_to_mysql(self, e):
        if self.is_syncing:
            self.show_snack_bar("Upload in progress, please wait.", ft.Colors.YELLOW_800)
            return
        self.is_syncing = True
        self.sync_button.disabled = True
        self.upload_button.disabled = True
        self.safe_update("disable_upload_buttons")
        db_config = {
            "host": "200.200.200.23",
            "user": "root",
            "password": "Pak@123",
            "database": "asm_sys"
        }
        conn_sqlite = None
        conn_mysql = None
        cursor_sqlite = None
        cursor_mysql = None
        try:
            conn_sqlite = sqlite3.connect(self.sqlite_db_path)
            conn_sqlite.row_factory = sqlite3.Row
            cursor_sqlite = conn_sqlite.cursor()
            cursor_sqlite.execute("SELECT * FROM job_cards")
            job_cards = [dict(row) for row in cursor_sqlite.fetchall()]
            
            conn_mysql = mysql.connector.connect(**db_config)
            cursor_mysql = conn_mysql.cursor()
            
            for jc in job_cards:
                original_job_number = jc['job_number']
                if '-' in jc['job_number'] and jc['job_number'].count('-') > 1:
                    parts = jc['job_number'].rsplit('-', 2)
                    if len(parts) == 3 and parts[-1].startswith('D'):
                        normalized_job_number = f"{parts[0]}-{parts[1]}"
                    else:
                        normalized_job_number = jc['job_number']
                else:
                    normalized_job_number = jc['job_number']
                
                if len(normalized_job_number) > 30:
                    self.show_snack_bar(f"Job number {normalized_job_number} too long for {jc['department_name']}", ft.Colors.RED_800)
                    continue
                
                cursor_mysql.execute("SELECT id FROM job_cards WHERE id = %s OR job_number = %s", (jc['id'], normalized_job_number))
                if cursor_mysql.fetchone():
                    continue
                
                cursor_mysql.execute("""
                    INSERT INTO job_cards (id, job_number, title, description, status, created_date, started_date,
                                           completed_date, entity_type, entity_id, closure_details, department_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    jc['id'], normalized_job_number, jc['title'], jc['description'], jc['status'], jc['created_date'],
                    jc['started_date'], jc['completed_date'], jc['entity_type'], jc['entity_id'],
                    jc['closure_details'], jc['department_name']
                ))
                cursor_sqlite.execute("UPDATE job_cards SET job_number = ? WHERE id = ?", (normalized_job_number, jc['id']))
                conn_sqlite.commit()
            
            conn_mysql.commit()
            self.show_snack_bar("Job cards uploaded successfully!", ft.Colors.TEAL_600)
            self.load_job_cards()
            try:
                self.page.add(Audio(src="https://www.soundjay.com/buttons/beep-01a.mp3", autoplay=True))
                if hasattr(self.page, 'top_bar_ref') and self.page.top_bar_ref.current:
                    self.page.top_bar_ref.current.update_notification_icon()
            except Exception as e:
                self.show_snack_bar(f"Error playing audio: {e}", ft.Colors.RED_800)
        except Error as e:
            if e.errno == 1406:
                self.show_snack_bar(f"Upload failed: Job number too long for {jc['department_name']}", ft.Colors.RED_800)
            elif e.errno == 1062:
                self.show_snack_bar(f"Upload failed: Duplicate job number {normalized_job_number}", ft.Colors.RED_800)
            elif e.errno == 2003:
                self.show_snack_bar("Upload failed: Cannot connect to database server", ft.Colors.RED_800)
            else:
                self.show_snack_bar(f"Upload failed: Database error - {e}", ft.Colors.RED_800)
        except Exception as e:
            self.show_snack_bar(f"Upload failed: {e}", ft.Colors.RED_800)
        finally:
            if cursor_sqlite:
                cursor_sqlite.close()
            if conn_sqlite:
                conn_sqlite.close()
            if cursor_mysql:
                cursor_mysql.close()
            if conn_mysql:
                conn_mysql.close()
            self.is_syncing = False
            self.sync_button.disabled = False
            self.upload_button.disabled = False
            self.safe_update("enable_upload_buttons")

    def filter_job_cards(self, e):
        self.selected_status = self.status_filter.value
        self.load_job_cards()

    def get_entity_info(self, entity_type, entity_id):
        db_config = {
            "host": "200.200.200.23",
            "user": "root",
            "password": "Pak@123",
            "database": "asm_sys"
        }
        conn = None
        cursor = None
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            if entity_type == "Asset":
                cursor.execute("SELECT serial_number, model FROM assets WHERE id = %s", (entity_id,))
                result = cursor.fetchone()
                return f"Asset: {result['serial_number']} ({result['model']})" if result else "Unknown Asset"
            elif entity_type == "Consumable":
                cursor.execute("""
                    SELECT c.cartridge_no, p.model AS printer_model
                    FROM deployed_consumables dc
                    JOIN consumables c ON dc.consumable_id = c.id
                    JOIN printers p ON dc.printer_id = p.id
                    WHERE dc.id = %s
                """, (entity_id,))
                result = cursor.fetchone()
                return f"Consumable: {result['cartridge_no']} (Printer: {result['printer_model']})" if result else "Unknown Consumable"
            elif entity_type == "Component":
                cursor.execute("SELECT serial_number, model FROM components WHERE id = %s", (entity_id,))
                result = cursor.fetchone()
                return f"Component: {result['serial_number']} ({result['model']})" if result else "Unknown Component"
            elif entity_type == "Device":
                cursor.execute("SELECT serial_number, model FROM devices WHERE id = %s", (entity_id,))
                result = cursor.fetchone()
                return f"Device: {result['serial_number']} ({result['model']})" if result else "Unknown Device"
            return "Unknown Entity"
        except Error:
            return "Error fetching entity info"
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def create_job_card_table(self):
        if not self.job_cards:
            return [ft.DataRow(cells=[
                ft.DataCell(ft.Text("No job cards found.", size=8, color=ft.Colors.RED_400)),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text(""))
            ])]
        rows = []
        for jc in self.job_cards:
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(jc.get('job_number', 'N/A')), size=8, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.DataCell(ft.Text(str(jc.get('title', 'N/A')), size=8, color=ft.Colors.BLACK, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.DataCell(ft.Text(str(jc.get('status', 'N/A')), size=8, color=ft.Colors.GREEN_700 if jc.get('status', '').lower() == 'open' else ft.Colors.YELLOW_700 if jc.get('status', '').lower() == 'started' else ft.Colors.BLUE_GREY_600, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                ft.DataCell(
                    ft.IconButton(
                        icon=ft.Icons.VISIBILITY,
                        icon_color=ft.Colors.BLUE_700,
                        icon_size=30,
                        tooltip="View Details",
                        on_click=lambda e, jc=jc: self.show_job_card_detail(jc),
                        data=jc.get('job_number', 'N/A')
                    )
                )
            ]))
        return rows

    def show_job_card_detail(self, job_card):
        try:
            created_date = job_card.get('created_date', 'N/A')
            if created_date and isinstance(created_date, str):
                try:
                    created_date = datetime.strptime(created_date, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M')
                except ValueError:
                    pass
            started_date = job_card.get('started_date', 'N/A')
            if started_date and isinstance(started_date, str):
                try:
                    started_date = datetime.strptime(started_date, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M')
                except ValueError:
                    pass
            completed_date = job_card.get('completed_date', 'N/A')
            if completed_date and isinstance(completed_date, str):
                try:
                    completed_date = datetime.strptime(completed_date, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M')
                except ValueError:
                    pass

            dialog_content = ft.Column(
                controls=[
                    ft.Text(f"Job No: {job_card.get('job_number', 'N/A')}", size=8, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_800),
                    ft.Text(f"ID: {job_card.get('id', 'N/A')}", size=8, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_800),
                    ft.Text(f"Title: {job_card.get('title', 'N/A')}", size=8, color=ft.Colors.BLACK, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"Description: {job_card.get('description', 'N/A')}", size=8, color=ft.Colors.BLACK, max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"Department: {job_card.get('department_name', 'N/A')}", size=8, color=ft.Colors.BLACK),
                    ft.Text(f"Entity: {job_card.get('entity_info', 'N/A')}", size=8, color=ft.Colors.BLACK, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"Closure: {job_card.get('closure_details', 'N/A')}", size=8, color=ft.Colors.BLACK, max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"Created: {created_date}", size=8, color=ft.Colors.BLACK),
                    ft.Text(f"Started: {started_date}", size=8, color=ft.Colors.BLACK),
                    ft.Text(f"Completed: {completed_date}", size=8, color=ft.Colors.BLACK),
                    ft.Text(f"Status: {job_card.get('status', 'N/A')}", size=8, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_800)
                ],
                spacing=5,
                scroll=ft.ScrollMode.AUTO
            )

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Details (ID: {job_card.get('id', 'N/A')})", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_800),
                content=ft.Container(
                    content=dialog_content,
                    width=340,
                    height=400,
                    padding=ft.padding.all(6),
                    bgcolor=ft.Colors.WHITE,
                    border_radius=8,
                    border=ft.border.all(1, ft.Colors.BLUE_GREY_200)
                ),
                actions=[
                    ft.TextButton(
                        "Close",
                        on_click=self.close_dialog,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.BLUE_600,
                            color=ft.Colors.WHITE,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            overlay_color=ft.Colors.BLUE_800
                        )
                    )
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                bgcolor=ft.Colors.BLUE_GREY_50,
                shape=ft.RoundedRectangleBorder(radius=10)
            )

            self.page.dialog = dialog
            dialog.open = True
            self.page.overlay.append(dialog)
            self.safe_update("show_job_card_detail")
        except Exception as e:
            self.show_snack_bar(f"Error opening job card details: {e}", ft.Colors.RED_800)

    def close_dialog(self, e):
        if self.page.dialog:
            self.page.dialog.open = False
            self.safe_update("close_dialog")

    def open_job_card_dialog(self, e=None):
        self.job_title = ft.TextField(
            label="Job Title",
            hint_text="Enter job title",
            border_color=ft.Colors.BLUE_300,
            color=ft.Colors.BLUE_900,
            text_size=8,
            max_lines=1,
            dense=True
        )
        self.job_description = ft.TextField(
            label="Description",
            hint_text="Enter job description",
            multiline=True,
            border_color=ft.Colors.BLUE_300,
            color=ft.Colors.BLUE_900,
            text_size=8,
            max_lines=3,
            dense=True
        )
        self.department_dropdown = ft.Dropdown(
            label="Department",
            options=[ft.dropdown.Option(key=str(d['id']), text=d['name']) for d in self.departments],
            value=str(self.departments[0]['id']) if self.departments else None,
            border_color=ft.Colors.BLUE_300,
            color=ft.Colors.BLUE_900,
            text_size=8,
            dense=True,
            menu_height=200
        )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Create Job Card", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_800),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        self.job_title,
                        self.job_description,
                        self.department_dropdown
                    ],
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO
                ),
                width=340,
                height=300,
                padding=ft.padding.all(6),
                bgcolor=ft.Colors.WHITE,
                border_radius=8,
                border=ft.border.all(1, ft.Colors.BLUE_GREY_200)
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=self.close_dialog,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.GREY_600,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8)
                    )
                ),
                ft.TextButton(
                    "Save",
                    on_click=self.save_job_card,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.TEAL_600,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8)
                    )
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=ft.Colors.BLUE_GREY_50,
            shape=ft.RoundedRectangleBorder(radius=10)
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.overlay.append(dialog)
        self.safe_update("open_job_card_dialog")

    def save_job_card(self, e):
        title = self.job_title.value.strip() if self.job_title.value else ""
        description = self.job_description.value.strip() if self.job_description.value else ""
        department_id = self.department_dropdown.value

        if not all([title, description, department_id]):
            self.show_snack_bar("Title, description, and department are required.", ft.Colors.RED_800)
            self.close_dialog(None)
            return

        db_config = {
            "host": "200.200.200.23",
            "user": "root",
            "password": "Pak@123",
            "database": "asm_sys"
        }
        conn_sqlite = None
        cursor_sqlite = None
        conn_mysql = None
        cursor_mysql = None
        max_attempts = 10
        attempt = 0
        job_id = None
        job_number = None
        is_offline = False

        try:
            conn_mysql = mysql.connector.connect(**db_config)
            cursor_mysql = conn_mysql.cursor()
            cursor_mysql.execute("SELECT name FROM department WHERE id = %s", (department_id,))
            department_data = cursor_mysql.fetchone()
            if not department_data:
                self.show_snack_bar("Invalid department selected.", ft.Colors.RED_800)
                self.close_dialog(None)
                return
            department_name = department_data[0]
            department_prefix = re.sub(r'[^a-zA-Z0-9]', '', department_name)[:10]

            current_date = datetime.now().strftime('%Y%m%d')
            while attempt < max_attempts:
                try:
                    cursor_mysql.execute("""
                        SELECT MAX(CAST(SUBSTRING(job_number, %s) AS UNSIGNED))
                        FROM job_cards
                        WHERE job_number LIKE %s
                    """, (len(department_prefix) + 9, f"{department_prefix}{current_date}-%"))
                    max_sequence = cursor_mysql.fetchone()[0]
                    count = (max_sequence or 0) + 1
                    job_number = f"{department_prefix}{current_date}-{count:04d}"
                    job_id = int(f"{department_id}{current_date}{count:04d}")

                    if len(job_number) > 30:
                        self.show_snack_bar(f"Job number {job_number} too long for {department_name}", ft.Colors.RED_800)
                        self.close_dialog(None)
                        return

                    cursor_mysql.execute("SELECT id FROM job_cards WHERE id = %s OR job_number = %s", (job_id, job_number))
                    if cursor_mysql.fetchone():
                        attempt += 1
                        continue
                    break
                except Error as mysql_err:
                    if attempt == max_attempts - 1:
                        self.show_snack_bar("MySQL unavailable, using device-specific job number", ft.Colors.YELLOW_800)
                        is_offline = True
                        conn_sqlite = sqlite3.connect(self.sqlite_db_path)
                        cursor_sqlite = conn_sqlite.cursor()
                        cursor_sqlite.execute("""
                            SELECT MAX(CAST(SUBSTRING(job_number, %s, 4) AS INTEGER))
                            FROM job_cards
                            WHERE job_number LIKE ?
                        """, (len(department_prefix) + 9, f"{department_prefix}{current_date}-%"))
                        max_sequence = cursor_sqlite.fetchone()[0]
                        count = (max_sequence or 0) + 1
                        job_number = f"{department_prefix}{current_date}-{count:04d}-D{self.device_id}"
                        if len(job_number) > 30:
                            self.show_snack_bar(f"Offline job number {job_number} too long for {department_name}", ft.Colors.RED_800)
                            self.close_dialog(None)
                            return
                        job_id = int(f"{department_id}{current_date}{count:04d}")
                        cursor_sqlite.close()
                        conn_sqlite.close()
                        cursor_sqlite = None
                        conn_sqlite = None
                        break
                    attempt += 1

            if attempt >= max_attempts and not is_offline:
                self.show_snack_bar("Unable to generate unique job ID after multiple attempts.", ft.Colors.RED_800)
                self.close_dialog(None)
                return

            conn_sqlite = sqlite3.connect(self.sqlite_db_path)
            cursor_sqlite = conn_sqlite.cursor()
            cursor_sqlite.execute("SELECT id FROM job_cards WHERE id = ? OR job_number = ?", (job_id, job_number))
            if cursor_sqlite.fetchone():
                self.show_snack_bar("Duplicate job ID or number detected in SQLite. Please try again.", ft.Colors.RED_800)
                self.close_dialog(None)
                return

            cursor_sqlite.execute("""
                INSERT INTO job_cards (id, job_number, title, description, status, created_date, department_name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (job_id, job_number, title, description, "Open", datetime.now().strftime('%Y-%m-%d %H:%M:%S'), department_name))
            conn_sqlite.commit()

            self.show_snack_bar("Job card created successfully!", ft.Colors.TEAL_600)
            self.load_job_cards()
            self.close_dialog(None)
            try:
                self.page.add(Audio(src="https://www.soundjay.com/buttons/beep-01a.mp3", autoplay=True))
                if hasattr(self.page, 'top_bar_ref') and self.page.top_bar_ref.current:
                    self.page.top_bar_ref.current.update_notification_icon()
            except Exception as e:
                self.show_snack_bar(f"Error playing audio or updating notification: {e}", ft.Colors.RED_800)
        except (sqlite3.Error, Error, Exception) as e:
            self.show_snack_bar(f"Error saving job card: {e}", ft.Colors.RED_800)
            self.close_dialog(None)
        finally:
            if cursor_sqlite:
                cursor_sqlite.close()
            if conn_sqlite:
                conn_sqlite.close()
            if cursor_mysql:
                cursor_mysql.close()
            if conn_mysql:
                conn_mysql.close()

    def show_snack_bar(self, message, color=ft.Colors.BLACK):
        self.snack_bar.content.value = message
        self.snack_bar.bgcolor = color
        self.snack_bar.open = False
        self.page.update()
        self.snack_bar.open = True
        self.page.update()

def main(page: ft.Page):
    page.title = "Job Card Management"
    page.window.maximized = False
    page.window.resizable = True
    page.window.width = 400
    page.window.height = 700
    page.bgcolor = ft.Colors.BLUE_GREY_50
    page.add(JobCardPage(page))

if __name__ == "__main__":
    ft.app(
        target=main,
        assets_dir="assets"
    )