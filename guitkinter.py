#
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
import tempfile, os, smtplib, sqlite3
from datetime import datetime
from escpos.printer import Usb
import win32print
import win32ui


#Fuctionality part\


def logout():
    pass
    # root.destroy()
    # os.system('python login.py')

# Barcode reader
def process_barcode(event=None):
    barcode = barcodeEntry.get().strip()
    if not barcode:
        return

    # Determine quantity (use Quantity entry if provided, otherwise 1)
    try:
        qty_text = phoneEntry.get().strip()
        qty = int(qty_text) if qty_text else 1
    except Exception:
        messagebox.showerror('Error', 'Invalid quantity', parent=root)
        barcodeEntry.delete(0, tk.END)
        return

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT id, medicine_name, price, quantity FROM inventory WHERE barcode = ?", (barcode,))
    row = cursor.fetchone()

    if not row:
        messagebox.showinfo('Not found', f'No product found for barcode: {barcode}', parent=root)
        conn.close()
        barcodeEntry.delete(0, tk.END)
        return

    item_id, name, price, available_qty = row

    if available_qty < qty:
        messagebox.showerror('Out of stock', f'Only {available_qty} available in stock.', parent=root)
        conn.close()
        barcodeEntry.delete(0, tk.END)
        return

    # Update database with decremented quantity
    new_qty = available_qty - qty
    cursor.execute("UPDATE inventory SET quantity = ? WHERE id = ?", (new_qty, item_id))
    conn.commit()
    conn.close()

    # Add to aggregated cart (this will rebuild the bill area)
    add_item_to_cart(item_id, name, price, qty)

    # Refresh items list and (if available) the inventory treeview
    try:
        readitems()
    except Exception:
        pass
    try:
        readintotreeview()
    except Exception:
        pass

    # Clear entries and reset focus
    barcodeEntry.delete(0, tk.END)
    phoneEntry.delete(0, tk.END)
    barcodeEntry.focus_set()

# Cart handling (aggregated by barcode/id)
cart = {}  # key: inventory id, value: {name, price, qty}

def add_item_to_cart(item_id, name, price, qty=1):
    global totalPrice
    # Update cart
    if item_id in cart:
        cart[item_id]['qty'] += qty
    else:
        cart[item_id] = {'name': name, 'price': float(price), 'qty': qty}

    # Rebuild bill area
    rebuild_bill_area()


def rebuild_bill_area():
    """Clear and re-render the textArea contents based on current cart."""
    global totalPrice
    global discountPrice, discountTax, discountCoupon

    # Configure a tag for the header
    textArea.tag_configure("header", font=("Arial", 15, "bold"),  justify="center")  # Center alignment
    # Configure a tag for centered text
    textArea.tag_configure("center", justify="center")


    textArea.delete(1.0, tk.END)
    # textArea.insert(1.0, '\t   ***Medical Store***\n\n')
    textArea.insert("1.0", "MEDICAL STORE\n\n", "header")
    textArea.insert(tk.END, "Odherwal Chowk near Shall Petrolium\n", "center")
    textArea.insert(tk.END, "Chakwal\n", "center")
    textArea.insert(tk.END, "NTN#9735369-6  Ph#0336-2127777\n", "center")
    textArea.insert(tk.END, "LIC#DSL-01-372-0008-99154p\n", "center")
    textArea.insert(tk.END, f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n', "center")
    # textArea.insert(tk.END, '\tContact # :0311-5552866\n\tEmail:mansoorpay@gmail.com\n')
    textArea.insert(tk.END, '========================================\n')
    textArea.insert(tk.END, ' Item \t     Unit \t  Quantity\t   Total \n')
    textArea.insert(tk.END, ' Name \t     Price \t\t         Price \n')
    textArea.insert(tk.END, '========================================\n')

    totalPrice = 0
    discountPrice = 0
    discountTax = 0
    discountCoupon = 0

    # discount_entry.get()
    for k, v in cart.items():
        name = v['name']
        price = v['price']
        qty = v['qty']
        line_total = int(price * qty)
        totalPrice += line_total
        textArea.insert(tk.END, f' {name}\t\t{price}\t{qty}\t{line_total}\n')
    # compute discounts and taxes after totalPrice is calculated
    def _get_percent(entry_widget):
        try:
            if entry_widget is not None and hasattr(entry_widget, 'get'):
                val = entry_widget.get().strip()
                if val.isdigit():
                    return int(val)
        except Exception:
            pass
        return 0

    d_pct = _get_percent(globals().get('discount_entry'))
    t_pct = _get_percent(globals().get('discount_tax'))
    c_pct = _get_percent(globals().get('discount_coupon'))

    discountPrice = (totalPrice * d_pct) / 100
    discountTax = (totalPrice * t_pct) / 100
    discountCoupon = (totalPrice * c_pct) / 100
    # keep totals footer consistent
    textArea.insert(tk.END, '\n')
    textArea.insert(tk.END, f'Total  \t\t\t\t{totalPrice} Rs\n')
    textArea.insert(tk.END, '----------------------------------------\n')
    textArea.insert(tk.END, f'GST  \t\t\t\t{discountTax} Rs\n')
    textArea.insert(tk.END, f'Discounts  \t\t\t\t{discountPrice} Rs\n')
    textArea.insert(tk.END, f'Coupons  \t\t\t\t{discountCoupon} Rs\n')
    textArea.insert(tk.END, '----------------------------------------\n')
    final_total = totalPrice + discountTax - discountPrice - discountCoupon
    textArea.insert(tk.END, f'Net Total  \t\t\t\t{final_total} Rs\n')
    textArea.insert(tk.END, 'Developed by Django Softwate PVT\n')
    textArea.insert(tk.END, 'Contact:92-311-5552866  Email:mansoorpay@gmail.com\n')

def get_db_path():
    """
    Returns the full path to the SQLite database file.
    Keeps DB path logic separate and reusable.
    """
    return os.path.join(os.path.dirname(__file__), "medicspharmacy.db")



def connectandcreatetable():
    # Connect to SQLite database and ensure schema has a barcode column
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    # Create table with barcode column (if not exists)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medicine_name TEXT NOT NULL,
        expiry DATE NOT NULL,
        barcode TEXT DEFAULT '',
        batch_no TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL
    );
    ''')

    # Ensure existing DB has barcode column (for older databases)
    cursor.execute("PRAGMA table_info(inventory);")
    cols = [row[1] for row in cursor.fetchall()]
    if 'barcode' not in cols:
        cursor.execute("ALTER TABLE inventory ADD COLUMN barcode TEXT;")

    conn.commit()
    conn.close()
connectandcreatetable()



def open_inventory_window():
    inventory_window = tk.Toplevel()
    inventory_window.title("Inventory Management")
    inventory_window.geometry("600x500")

    headingLabel = tk.Label(inventory_window, text="Inventory Management", font=('times new roman', 30, 'bold'), background='gray20', foreground='gold', bd=12, relief=tk.GROOVE)
    headingLabel.pack(fill=tk.X, pady=5)

    # Project Details
    treeviewFrame = tk.Frame(inventory_window, background='gray20', bd=8, relief=tk.GROOVE)
    treeviewFrame.pack(fill=tk.X, pady=5)

    columns = ('#1', '#2', '#3', '#4', '#5', '#6', '#7')
    tree = ttk.Treeview(treeviewFrame, columns=columns, show='headings')
    tree.heading('#1', text='Sr')
    tree.heading('#2', text='Medicine Name')
    tree.heading('#3', text='Expiry')
    tree.heading('#4', text='Barcode')
    tree.heading('#5', text='Batch Number')
    tree.heading('#6', text='Quantity')
    tree.heading('#7', text='Price')

    # Setting column widths
    tree.column('#1', width=30)
    tree.column('#2', width=150)
    tree.column('#3', width=100)
    tree.column('#4', width=120)
    tree.column('#5', width=100)
    tree.column('#6', width=70)
    tree.column('#7', width=70)

    # Adding Vertical Scrollbar
    vsb = ttk.Scrollbar(treeviewFrame, orient="vertical", command=tree.yview)
    vsb.pack(side='right', fill='y')
    tree.configure(yscrollcommand=vsb.set)

    # Adding Horizontal Scrollbar
    hsb = ttk.Scrollbar(treeviewFrame, orient="horizontal", command=tree.xview)
    hsb.pack(side='bottom', fill='x')
    tree.configure(xscrollcommand=hsb.set)
    tree.pack(fill='both', expand=True)

    # Configure Treeview Style 
    style = ttk.Style() 
    style.configure("Treeview", rowheight=25) 
    style.configure("Treeview.Heading", font=('Calibri', 10,'bold')) 
    style.map('Treeview', background=[('selected', 'blue')])

    def clear_treeview():
        for item in tree.get_children():
            tree.delete(item)

    # Reading Data from DB and inserting into Treeview
    def readintotreeview():
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM inventory;")
        completeRow = cursor.fetchall()

        conn.close()

        clear_treeview()

        # projectsList.delete(0, tk.END)
        tree.tag_configure('low', background='red', foreground='white')
        for record in completeRow:
            # record indices: id(0), medicine_name(1), expiry(2), barcode(3), batch_no(4), quantity(5), price(6)
            tag = "low" if record[5] < 10 else ""
            tree.insert('', 'end', values=(record[0], record[1], record[2], record[3], record[4], record[5], record[6]), tags=(tag,))

    
    readintotreeview()
    
    # Function to open new entry window
    def open_new_entry_window():
        new_entry_window = tk.Toplevel(inventory_window)
        new_entry_window.title("New Entry")
        new_entry_window.geometry("550x450")

        headingLabel = tk.Label(new_entry_window, text="New Entry", font=('times new roman', 30, 'bold'), background='gray20', foreground='gold', bd=12, relief=tk.GROOVE)
        headingLabel.pack(fill=tk.X, pady=5)

        # Create form labels and entries
        newentryFrame = tk.Frame(new_entry_window, background='gray20', bd=8, relief=tk.GROOVE)
        newentryFrame.pack(fill=tk.X, pady=5)
        
        tk.Label(newentryFrame, text="Medicine Name",font=('times new roman',15,'bold'),background='gray20',foreground='white').grid(row=0, column=0, padx=10, pady=5)
        medicine_name_entry = tk.Entry(newentryFrame,font=('arial',15),bd=7,width=18)
        medicine_name_entry.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(newentryFrame, text="Expiry Date (YYYY-MM-DD)",font=('times new roman',15,'bold'),background='gray20',foreground='white').grid(row=1, column=0, padx=10, pady=5)
        expiry_entry = tk.Entry(newentryFrame,font=('arial',15),bd=7,width=18)
        expiry_entry.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(newentryFrame, text="Barcode",font=('times new roman',15,'bold'),background='gray20',foreground='white').grid(row=2, column=0, padx=10, pady=5)
        barcode_entry = tk.Entry(newentryFrame,font=('arial',15),bd=7,width=18)
        barcode_entry.grid(row=2, column=1, padx=10, pady=5)

        tk.Label(newentryFrame, text="Batch No",font=('times new roman',15,'bold'),background='gray20',foreground='white').grid(row=3, column=0, padx=10, pady=5)
        batch_no_entry = tk.Entry(newentryFrame,font=('arial',15),bd=7,width=18)
        batch_no_entry.grid(row=3, column=1, padx=10, pady=5)

        tk.Label(newentryFrame, text="Quantity",font=('times new roman',15,'bold'),background='gray20',foreground='white').grid(row=4, column=0, padx=10, pady=5)
        quantity_entry = tk.Entry(newentryFrame,font=('arial',15),bd=7,width=18)
        quantity_entry.grid(row=4, column=1, padx=10, pady=5)

        tk.Label(newentryFrame, text="Price",font=('times new roman',15,'bold'),background='gray20',foreground='white').grid(row=5, column=0, padx=10, pady=5)
        price_entry = tk.Entry(newentryFrame,font=('arial',15),bd=7,width=18)
        price_entry.grid(row=5, column=1, padx=10, pady=5)

        # Function to insert data into database
        def add_entry():
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO inventory (medicine_name, expiry, barcode, batch_no, quantity, price)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (medicine_name_entry.get(), expiry_entry.get(), barcode_entry.get(), batch_no_entry.get(), quantity_entry.get(), price_entry.get()))
            conn.commit()
            new_id = cursor.lastrowid
            conn.close()
            # Insert new data into Treeview 
            # tree.insert('', 'end', values=(new_id, medicine_name_entry.get(), expiry_entry.get(), barcode_entry.get(), batch_no_entry.get(), quantity_entry.get(), price_entry.get()))
            readintotreeview() 
            readitems()
            new_entry_window.destroy()

        # Add submit button
        submit_button = tk.Button(newentryFrame, text="Submit", font=('arial', 16, 'bold'), background="gray20", foreground='white', bd=5, width=8, pady=10,command=add_entry)
        submit_button.grid(row=6, column=0, columnspan=2, pady=10)

    # Add edit, delete, update buttons
    def edit_item():
        pass  # Add your logic here

    # def delete_item():
    #     pass  # Add your logic here
    def delete_item():
        selected_item = tree.selection()[0]  # Get selected item
        item_values = tree.item(selected_item, 'values')  # Get values of the selected item
        item_id = item_values[0]  # Assuming 'id' is the first value in the tuple

        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM inventory WHERE id = ?
        ''', (item_id,))
        conn.commit()
        conn.close()

        # tree.delete(selected_item)  # Remove the item from Treeview
        readintotreeview()
        readitems()


    def update_item():
        selected_item = tree.selection()[0]
        values = tree.item(selected_item, 'values')

        update_window = tk.Toplevel(inventory_window)
        update_window.title("Update Entry")
        update_window.geometry("450x420")

        headingLabel = tk.Label(update_window, text="Edit", font=('times new roman', 30, 'bold'), background='gray20', foreground='gold', bd=12, relief=tk.GROOVE)
        headingLabel.pack(fill=tk.X, pady=5)

        # Create form labels and entries
        editentryFrame = tk.Frame(update_window, background='gray20', bd=8, relief=tk.GROOVE)
        editentryFrame.pack(fill=tk.X, pady=5)

        tk.Label(editentryFrame, text="Medicine Name", font=('times new roman',15,'bold'),background='gray20',foreground='white').grid(row=0, column=0, padx=10, pady=5)
        med_name_entry = tk.Entry(editentryFrame,font=('arial',15),bd=7,width=18)
        med_name_entry.grid(row=0, column=1, padx=10, pady=5)
        med_name_entry.insert(0, values[1])

        tk.Label(editentryFrame, text="Expiry", font=('times new roman',15,'bold'),background='gray20',foreground='white').grid(row=1, column=0, padx=10, pady=5)
        expiry_entry = tk.Entry(editentryFrame,font=('arial',15),bd=7,width=18)
        expiry_entry.grid(row=1, column=1, padx=10, pady=5)
        expiry_entry.insert(0, values[2])

        tk.Label(editentryFrame, text="Barcode", font=('times new roman',15,'bold'),background='gray20',foreground='white').grid(row=2, column=0, padx=10, pady=5)
        barcode_entry = tk.Entry(editentryFrame,font=('arial',15),bd=7,width=18)
        barcode_entry.grid(row=2, column=1, padx=10, pady=5)
        barcode_entry.insert(0, values[3])

        tk.Label(editentryFrame, text="Batch No", font=('times new roman',15,'bold'),background='gray20',foreground='white').grid(row=3, column=0, padx=10, pady=5)
        batch_no_entry = tk.Entry(editentryFrame,font=('arial',15),bd=7,width=18)
        batch_no_entry.grid(row=3, column=1, padx=10, pady=5)
        batch_no_entry.insert(0, values[4])

        tk.Label(editentryFrame, text="Quantity", font=('times new roman',15,'bold'),background='gray20',foreground='white').grid(row=4, column=0, padx=10, pady=5)
        quantity_entry = tk.Entry(editentryFrame,font=('arial',15),bd=7,width=18)
        quantity_entry.grid(row=4, column=1, padx=10, pady=5)
        quantity_entry.insert(0, values[5])

        tk.Label(editentryFrame, text="Price", font=('times new roman',15,'bold'),background='gray20',foreground='white').grid(row=5, column=0, padx=10, pady=5)
        price_entry = tk.Entry(editentryFrame,font=('arial',15),bd=7,width=18)
        price_entry.grid(row=5, column=1, padx=10, pady=5)
        price_entry.insert(0, values[6])

        def save_changes():
            conn = sqlite3.connect(get_db_path())
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE inventory
                SET medicine_name=?, expiry=?, barcode=?, batch_no=?, quantity=?, price=?
                WHERE id=?
            ''', (med_name_entry.get(), expiry_entry.get(), barcode_entry.get(), batch_no_entry.get(), quantity_entry.get(), price_entry.get(), values[0]))
            conn.commit()
            conn.close()

            # Update Treeview
            # tree.item(selected_item, values=(values[0], med_name_entry.get(), expiry_entry.get(), batch_no_entry.get(), quantity_entry.get(), price_entry.get()))
            readintotreeview()
            readitems()
            update_window.destroy()

        tk.Button(editentryFrame, text="Save", font=('arial', 12, 'bold'), background="gray20", foreground='white', bd=5, width=8, pady=10,command=save_changes).grid(row=5, column=0, columnspan=2, pady=10)

    inventorybuttonFrame = tk.Frame(inventory_window, background='gray20', bd=8, relief=tk.GROOVE)
    inventorybuttonFrame.pack(fill=tk.X, pady=5)

    # Buttons
    add_button = tk.Button(inventorybuttonFrame, text="New Entry", font=('arial', 16, 'bold'), background="gray20", foreground='white', bd=5, width=8, pady=10, command=open_new_entry_window)
    add_button.pack(side='left')

    edit_button = tk.Button(inventorybuttonFrame, text="Edit", font=('arial', 16, 'bold'), background="gray20", foreground='white', bd=5, width=8, pady=10, command=edit_item)
    edit_button.pack(side='left')

    delete_button = tk.Button(inventorybuttonFrame, text="Delete", font=('arial', 16, 'bold'), background="gray20", foreground='white', bd=5, width=8, pady=10, command=delete_item)
    delete_button.pack(side='left')

    update_button = tk.Button(inventorybuttonFrame, text="Update", font=('arial', 16, 'bold'), background="gray20", foreground='white', bd=5, width=8, pady=10, command=update_item)
    update_button.pack(side='left')

    print_button = tk.Button(inventorybuttonFrame, text="Print", font=('arial', 16, 'bold'), background="gray20", foreground='white', bd=5, width=8, pady=10, command=print_bill)
    print_button.pack(side='left')



# Function to update Listbox based on search
def update_listbox(event):
    search_term = search_entry.get()
    results = fetch_data(search_term)
    projectsList.delete(0, tk.END)
    for result in results:
        projectsList.insert(tk.END, result[0])

# Function to search and update Listbox
def fetch_data(search_term):

    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT medicine_name FROM inventory WHERE medicine_name LIKE ?", ('%' + search_term + '%',))
    results = cursor.fetchall()
    conn.close()
    return results

def send_email():
    def send_gmail():
        try:
            ob = smtplib.SMTP('smtp.gmail.com', 587)
            ob.starttls()
            ob.login(senderEntry.get(), passwordEntry.get())
            message = emailtextArea.get('1.0', tk.END)
            receiverAdress = receiverEntry.get()
            ob.sendmail(senderEntry.get(), receiverAdress, message)
            ob.quit()
            messagebox.showinfo('Successful', 'Email sent!',parent = root1)
            root1.destroy()
        except:
            messagebox.showinfo('Failed', 'Please try again!',parent =root1)



    if textArea.get(1.0,tk.END) == '\n':
        messagebox.showerror('Error','Nothing in Email')
    else:
        root1 = tk.Toplevel()
        root1.grab_set()
        root1.title("Send Email")
        root1.resizable(False, False)
        root1.configure(bg="grey20")

        senderFrame = tk.LabelFrame(root1,text = 'SENDER',font = ('arial',16,'bold'),background='grey20',foreground ='white')
        senderFrame.grid(row = 0, column = 0,padx = 40,pady = 20)

        senderLabel = tk.Label(senderFrame, text = "Sender's Email ID", font = ('arial',14,'bold'),background='grey20',foreground ='white')
        senderLabel.grid(row = 0, column = 0,padx = 10 ,pady = 8)
        senderEntry = tk.Entry(senderFrame,font = ('arial',14,'bold'),bd = 2,width = 23, relief = tk.RIDGE)
        senderEntry.grid(row = 0, column = 1,padx = 10 ,pady = 8)

        passwordLabel = tk.Label(senderFrame, text="Password", font=('arial', 14, 'bold'), background='grey20',
                            foreground='white')
        passwordLabel.grid(row=1, column=0, padx=10, pady=8)
        passwordEntry = tk.Entry(senderFrame, font=('arial', 14, 'bold'), bd=2, width=23, relief=tk.RIDGE,show='*')
        passwordEntry.grid(row=1, column=1, padx=10, pady=8)

        #Receiver Email Entry
        receiverFrame = tk.LabelFrame(root1, text='RECIPIENT', font=('arial', 16, 'bold'), background='grey20', foreground='white')
        receiverFrame.grid(row=1, column=0, padx=40, pady=20)

        receiverLabel = tk.Label(receiverFrame, text="Email Address", font=('arial', 14, 'bold'), background='grey20',
                            foreground='white')
        receiverLabel.grid(row=0, column=0, padx=10, pady=8)
        receiverEntry = tk.Entry(receiverFrame, font=('arial', 14, 'bold'), bd=2, width=23, relief=tk.RIDGE)
        receiverEntry.grid(row=0, column=1, padx=10, pady=8)

        #Message
        messageLabel = tk.Label(receiverFrame, text="Message", font=('arial', 14, 'bold'), background='grey20',
                            foreground='white')
        messageLabel.grid(row=1, column=0, padx=10, pady=8)

        emailtextArea = tk.Text(receiverFrame, font=('arial', 14, 'bold'), bd = 2, relief=tk.SUNKEN,width=42,height=11)
        emailtextArea.grid(row=2, column=0, padx=10, pady=8,columnspan =2)
        emailtextArea.delete('1.0',tk.END)
        emailtextArea.insert(tk.END,textArea.get('1.0', tk.END).replace('=','').replace('-','').replace('\t\t\t ','\t\t'))

        sendButton = tk.Button(root1,text='SEND',font=('arial', 16, 'bold'),width=15,command=send_gmail)
        sendButton.grid(row=2, column=0, padx=10, pady=8)


        root1.mainloop()


def get_receipt_text(cart, totalPrice, discount):
    # print("Generating receipt text...")
    lines = []

    # ===== Header (without MEDICAL STORE, handled in ESC/POS) =====
    lines.append("Odherwal Chowk near Shall Petrolium")
    lines.append("Chakwal")
    lines.append("NTN#9735369-6   Ph#0336-2127777")
    lines.append("LIC#DSL-01-372-0008-99154p")
    lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 40)

    # ===== Column Titles =====
    lines.append(f"{'Item':12}{'Unit':>6}{'Qty':>4}{'Total':>8}")
    lines.append("=" * 40)

    # ===== Items =====
    for v in cart.values():
        name = v['name'][:12]   # truncate to fit
        price = v['price']
        qty = v['qty']
        line_total = int(price * qty)
        lines.append(f"{name:12}{price:>6}{qty:>4}{line_total:>8}")

    lines.append("=" * 40)

    # ===== Totals =====
    lines.append(f"{'Subtotal':20}{totalPrice:>10} Rs")
    if discount > 0:
        lines.append(f"{'Discount':20}-{discount:>9} Rs")
        lines.append(f"{'Grand Total':20}{totalPrice-discount:>10} Rs")
    else:
        lines.append(f"{'Grand Total':20}{totalPrice:>10} Rs")

    lines.append("-" * 40)

    # ===== Footer (will be centered in ESC/POS) =====
    lines.append("Developed by Aziqsolutions")
    lines.append("Thank you for your purchase!")

    return "\n".join(lines)


# def print_receipt_thermal():
#     try:
#         receipt_text = get_receipt_text(cart, totalPrice, discountPrice + discountCoupon)

#         ESC = b'\x1b'
#         GS  = b'\x1d'

#         data = b""
#         data += ESC + b"@"                      # Initialize printer

#         # ===== Big Bold Title =====
#         data += ESC + b"a" + b"\x01"            # Center alignment
#         data += ESC + b"E" + b"\x01"            # Bold on
#         data += ESC + b"!" + b"\x10"            # Double height & width
#         data += b"MEDICAL STORE\n"
#         data += ESC + b"!" + b"\x00"            # Normal size
#         data += ESC + b"E" + b"\x00"            # Bold off

#         # ===== Centered Header (address, date) =====
#         data += ESC + b"a" + b"\x01"            # Center alignment
#         header_lines = receipt_text.split("\n")[0:5]  # first 5 lines
#         for line in header_lines:
#             data += line.encode("ascii", "ignore") + b"\n"

#         # ===== Left-aligned body (items, totals) =====
#         data += ESC + b"a" + b"\x00"
#         body_lines = receipt_text.split("\n")[5:-2]   # middle lines
#         for line in body_lines:
#             data += line.encode("ascii", "ignore") + b"\n"

#         # ===== Centered Footer =====
#         data += ESC + b"a" + b"\x01"
#         footer_lines = receipt_text.split("\n")[-2:]
#         for line in footer_lines:
#             data += line.encode("ascii", "ignore") + b"\n"

#         # Feed and cut
#         data += b"\n\n"
#         data += GS + b"V" + b"\x00"

#         # Send to printer
#         printer_name = win32print.GetDefaultPrinter()
#         hPrinter = win32print.OpenPrinter(printer_name)
#         hJob = win32print.StartDocPrinter(hPrinter, 1, ("Receipt", None, "RAW"))
#         win32print.StartPagePrinter(hPrinter)
#         win32print.WritePrinter(hPrinter, data)
#         win32print.EndPagePrinter(hPrinter)
#         win32print.EndDocPrinter(hPrinter)
#         win32print.ClosePrinter(hPrinter)

#     except Exception as e:
#         print(f"Print Error: {e}")

import win32print
from datetime import datetime

def print_receipt_thermal():
    try:
        receipt_text = get_receipt_text(cart, totalPrice, discountPrice + discountCoupon)

        ESC = b'\x1b'
        GS  = b'\x1d'

        data = b""
        data += ESC + b"@"                      # Initialize printer

        # ===== Big Bold Title =====
        data += ESC + b"a" + b"\x01"            # Center alignment
        data += ESC + b"E" + b"\x01"            # Bold on
        data += ESC + b"!" + b"\x10"            # Double height & width
        data += b"MEDICAL STORE\n"
        data += ESC + b"!" + b"\x00"            # Normal size
        data += ESC + b"E" + b"\x00"            # Bold off

        # ===== Centered Header =====
        data += ESC + b"a" + b"\x01"
        header_lines = receipt_text.split("\n")[0:5]
        for line in header_lines:
            data += line.encode("ascii", "ignore") + b"\n"

        # ===== Left-aligned Body =====
        data += ESC + b"a" + b"\x00"
        body_lines = receipt_text.split("\n")[5:-2]
        for line in body_lines:
            data += line.encode("ascii", "ignore") + b"\n"

        # ===== Centered Footer =====
        data += ESC + b"a" + b"\x01"
        footer_lines = receipt_text.split("\n")[-2:]
        for line in footer_lines:
            data += line.encode("ascii", "ignore") + b"\n"

        # ===== QR Code (your website) =====
        qr_data = "https://www.aziqsolutions.com"
        qr_bytes = qr_data.encode("utf-8")

        # Select model
        data += GS + b"(k" + b"\x04\x00" + b"1A" + b"\x02\x00"
        # Set size of module (1–16)
        data += GS + b"(k" + b"\x03\x00" + b"1C" + b"\x06"
        # Store data
        length = len(qr_bytes) + 3
        pL = length % 256
        pH = length // 256
        data += GS + b"(k" + bytes([pL, pH]) + b"1P0" + qr_bytes
        # Print QR code
        data += GS + b"(k" + b"\x03\x00" + b"1Q0"

        # Feed and cut
        data += b"\n\n"
        data += GS + b"V" + b"\x00"

        # Send to printer
        printer_name = win32print.GetDefaultPrinter()
        hPrinter = win32print.OpenPrinter(printer_name)
        hJob = win32print.StartDocPrinter(hPrinter, 1, ("Receipt", None, "RAW"))
        win32print.StartPagePrinter(hPrinter)
        win32print.WritePrinter(hPrinter, data)
        win32print.EndPagePrinter(hPrinter)
        win32print.EndDocPrinter(hPrinter)
        win32print.ClosePrinter(hPrinter)

    except Exception as e:
        print(f"Print Error: {e}")

def clearAll():
    global totalPrice, cart
    totalPrice  = 0
    cart.clear()
    # Safely clear user input fields without depending on variable ordering
    for w in ('barcodeEntry', 'phoneEntry', 'billEntry', 'discount_name_entry', 'discount_qty_entry', 'discount_price_entry'):
        try:
            globals()[w].delete(0, tk.END)
        except Exception:
            pass
    rebuild_bill_area()


def total():
    # Rebuild and show total in a message for clarity
    rebuild_bill_area()
    messagebox.showinfo('Total', f'Total: {totalPrice} Rs')



def readitems():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()

    cursor.execute("SELECT medicine_name FROM inventory;")
    # tree.insert('', 'end', values=(new_id, medicine_name_entry.get(), expiry_entry.get(), batch_no_entry.get(), quantity_entry.get(), price_entry.get())) 
        
    records = cursor.fetchall()

    conn.close()

    projectsList.delete(0, tk.END)
    for record in records:
        projectsList.insert(tk.END, f'{record[0]}')


def on_select(event):

    selectedIndex = projectsList.curselection()

    if selectedIndex:
        item = projectsList.get(selectedIndex)
        query = "SELECT id, price, quantity FROM inventory WHERE medicine_name = ?"

        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute(query, (item,))
        result = cursor.fetchone()

        if result is None:
            messagebox.showerror('Error', 'No matching record found.')
            conn.close()
            return

        item_id, priceofitem, quantityofitem = result

        itemQuantity = simpledialog.askstring("Input", "Enter Quantity:", initialvalue="1")
        if not itemQuantity:
            conn.close()
            return

        try:
            q = int(itemQuantity)
        except Exception:
            messagebox.showerror('Error', 'Invalid quantity')
            conn.close()
            return

        if q > quantityofitem:
            messagebox.showerror('Out of stock', f'Only {quantityofitem} available in stock.')
            conn.close()
            return

        # Update DB
        remainingitemQuantity = quantityofitem - q
        cursor.execute('''
            UPDATE inventory
            SET quantity=? 
            WHERE id =?
        ''', (remainingitemQuantity, item_id))
        conn.commit()
        conn.close()

        # Add to aggregated cart
        add_item_to_cart(item_id, item, priceofitem, q)

    else:
        messagebox.showinfo('Not Found','Unknown Error')

totalPrice = 0



# GUI Part
root = tk.Tk()
root.title("Offline Software Managment System - Medical Store")


root.geometry('1270x800')
#root.iconbitmap("icon.ico")
headingLabel= tk.Label(root,text="Medical Store",font=('times new roman',30,'bold'),background='gray20',foreground='gold',bd=12,relief=tk.GROOVE)
headingLabel.pack(fill=tk.X,pady=5)


# Customers Details Frame
costumer_details_frame = tk.LabelFrame(root,text="New Entry",font=('times new roman',15,'bold'),foreground='gold',bd=8,relief=tk.GROOVE,background='gray20')
costumer_details_frame.pack(fill=tk.X)

nameLabel=tk.Label(costumer_details_frame,text='Barcode',font=('times new roman',15,'bold'),background='gray20',foreground='white')
nameLabel.grid(row=0,column=0,padx=20)

barcodeEntry=tk.Entry(costumer_details_frame,font=('arial',15),bd=7,width=18)
barcodeEntry.grid(row=0,column=1,padx=8)
barcodeEntry.bind("<Return>", process_barcode)
barcodeEntry.focus_set()


phoneLabel=tk.Label(costumer_details_frame,text='Quantity',font=('times new roman',15,'bold'),background='gray20',foreground='white')
phoneLabel.grid(row=0,column=2,padx=20,pady=2)

phoneEntry=tk.Entry(costumer_details_frame,font=('arial',15),bd=7,width=18)
phoneEntry.grid(row=0,column=3,padx=8)

billnumberLabel=tk.Label(costumer_details_frame,text='Price',font=('times new roman',15,'bold'),background='gray20',foreground='white')
billnumberLabel.grid(row=0,column=4,padx=20,pady=2)

billEntry=tk.Entry(costumer_details_frame,font=('arial',15),bd=7,width=18)
billEntry.grid(row=0,column=5,padx=8)

submitButton= tk.Button(costumer_details_frame,text="Inventory",font=('arial',12,'bold'),bd=7,width=10,command=open_inventory_window)
submitButton.grid(row=0,column=6,padx=20)

#Project Details
projectPanel = tk.Frame(root,background='gray20')
projectPanel.pack(fill= tk.X,pady=5)


items_details_frame = tk.LabelFrame(projectPanel,text="Items",font=('times new roman',15,'bold'),foreground='gold',bd=8,relief=tk.GROOVE,background='gray20')
items_details_frame.grid(row=0,column=0,padx=25)

#Listbox
search_entry = tk.Entry(items_details_frame,  width=30,font=('arial',15),bd=7)
search_entry.bind("<KeyRelease>", update_listbox)
search_entry.grid(row=0,column=0,padx=5)
projectsList = tk.Listbox(items_details_frame,bd=5,font=('arial',15,),height=15,width=30,relief=tk.GROOVE)
projectsList.bind('<Return>',on_select)
projectsList.grid(row=1,column=0,padx=5)

#Bill Area
billFrame=tk.Frame(projectPanel,bd=8,relief=tk.GROOVE)
billFrame.grid(row=0,column=2,padx=25,pady = 5)
bill_details_frame = tk.Label(billFrame,text="Bill",font=('times new roman',15,'bold'),bd=8,relief=tk.GROOVE)
bill_details_frame.pack(fill=tk.X)
scrollbar=tk.Scrollbar(billFrame,orient=tk.VERTICAL)
scrollbar.pack(side=tk.RIGHT,fill=tk.Y)
textArea = tk.Text(billFrame,height=20,width=40,yscrollcommand=scrollbar.set)
textArea.pack()
scrollbar.config(command=textArea.yview)
# Initialize bill area
rebuild_bill_area()
readitems()


#Bill menu frame

billmenuframe = tk.LabelFrame(projectPanel,text="Controls",font=('times new roman',15,'bold'),foreground='gold',bd=8,relief=tk.GROOVE,background='gray20')
billmenuframe.grid(row=0,column=1,padx=20)

totalbutton=tk.Button(billmenuframe,text="Total",font=('arial',16,'bold'),background="gray20",
                foreground='white',bd=5,width=8,pady=10,command=total)
totalbutton.grid(row=0,column=0,pady=5,padx=10)

billbutton=tk.Button(billmenuframe,text="logout",font=('arial',16,'bold'),background="gray20",
                        foreground='white',bd=5,width=8,pady=10, command=logout)
billbutton.grid(row=1,column=0,pady=5,padx=10)

emailbutton=tk.Button(billmenuframe,text="Email",font=('arial',16,'bold'),background="gray20",
                foreground='white',bd=5,width=8,pady=10,command=send_email)
emailbutton.grid(row=2,column=0,pady=5,padx=10)

printbutton=tk.Button(billmenuframe,text="Print",font=('arial',16,'bold'),background="gray20",
                foreground='white',bd=5,width=8,pady=10,command=print_receipt_thermal)
printbutton.grid(row=3,column=0,pady=5,padx=10)

clearbutton=tk.Button(billmenuframe,text="Clear",font=('arial',16,'bold'),background="gray20",
                foreground='white',bd=5,width=8,pady=10,command=clearAll)
clearbutton.grid(row=4,column=0,pady=5,padx=10)



# 
taxFrame = tk.LabelFrame(root,text="Discounts and Tax",font=('times new roman',15,'bold'),foreground='gold',bd=8,relief=tk.GROOVE,background='gray20')
taxFrame.pack(fill=tk.X)

# Discount / tax controls (use unique names to avoid clobbering main inputs)
discount_item_label = tk.Label(taxFrame, text='Discount', font=('times new roman',15,'bold'), background='gray20', foreground='white')
discount_item_label.grid(row=0, column=0, padx=20)

discount_entry = tk.Entry(taxFrame, font=('arial',15), bd=7, width=18)
discount_entry.grid(row=0, column=1, padx=8)

discount_qty_label = tk.Label(taxFrame, text='Tax', font=('times new roman',15,'bold'), background='gray20', foreground='white')
discount_qty_label.grid(row=0, column=2, padx=20, pady=2)

discount_tax = tk.Entry(taxFrame, font=('arial',15), bd=7, width=18)
discount_tax.grid(row=0, column=3, padx=8)

discount_price_label = tk.Label(taxFrame, text='Coupon', font=('times new roman',15,'bold'), background='gray20', foreground='white')
discount_price_label.grid(row=0, column=4, padx=20, pady=2)

discount_coupon = tk.Entry(taxFrame, font=('arial',15), bd=7, width=18)
discount_coupon.grid(row=0, column=5, padx=8)




root.mainloop()
