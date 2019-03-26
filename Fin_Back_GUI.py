import tkinter
from tkinter import ttk
import datetime
import pytz
import sqlite3
import locale
import tzlocal


db = sqlite3.connect("main_database.sqlite", detect_types=sqlite3.PARSE_DECLTYPES)

db.execute("CREATE TABLE IF NOT EXISTS accounts (name TEXT PRIMARY KEY NOT NULL, currency TEXT NOT NULL, card_bal INTEGER NOT NULL,"
           " cash_bal INTEGER NOT NULL)")
db.execute("CREATE TABLE IF NOT EXISTS history (time TIMESTAMP NOT NULL,"
           " account TEXT NOT NULL, amount INTEGER NOT NULL, category TEXT NOT NULL,"
           " bal_type TEXT NOT NULL, subcateg TEXT NOT NULL, comment TEXT, PRIMARY KEY (time, account))")


class Account(object):

    @staticmethod
    def _current_time():
        return pytz.utc.localize(datetime.datetime.utcnow())

    @staticmethod
    def retrieve_account(name):
        cursor = db.execute("SELECT name, currency, card_bal, cash_bal FROM accounts WHERE (name = ?)", (name,))
        row_retrieved = cursor.fetchone()
        return row_retrieved

    def display_all_transac(self):
        cursor = db.execute("SELECT strftime('%Y-%m-%d %H:%M:%S', history.time, 'localtime'),"
                            " history.account, history.category, history.amount, history.bal_type, history.subcateg,"
                            " history.comment"
                            " FROM history WHERE (account = ?) ORDER BY history.time", (self.name,))
        all_transac = cursor.fetchall()
        return all_transac

    def __init__(self, name: str, currency: str, opening_card_balance: int = 0, opening_cash_balance: int = 0):
        data = Account.retrieve_account(name)
        global init_message
        if data:
            self.name, self.currency, self._card_bal, self._cash_bal = data
            self._balance = (self._card_bal/100) + (self._cash_bal/100)
            locale.setlocale(locale.LC_ALL, self.currency)
            init_message = "Retrieved record for {}. Total balance is {} (Card:{} + Cash:{})"\
                .format(self.name, locale.currency(self._balance, grouping=True),
                        locale.currency(self._card_bal/100, grouping=True, symbol=False),
                        locale.currency(self._cash_bal/100, grouping=True, symbol=False))
            print(init_message)

        else:
            locale.setlocale(locale.LC_ALL, currency)
            self.name = name
            self._card_bal = opening_card_balance
            self._cash_bal = opening_cash_balance
            self._balance = (self._card_bal/100) + (self._cash_bal/100)
            cursor = db.execute("INSERT INTO accounts VALUES(?, ?, ?, ?)", (name, currency, opening_card_balance, opening_cash_balance))
            cursor.connection.commit()
            init_message = "Account created for {}.\nTotal balance is {}\n(Card:{:.2f} + Cash:{:.2f})"\
                .format(self.name, locale.currency(self._balance, grouping=True), self._card_bal/100, self._cash_bal/100)
            print(init_message)

    def show_balance(self):
        print("Total Balance on account {} is {} (Card:{} + Cash:{})".format(self.name,
                                                                             locale.currency(self._balance, grouping=True),
                                                                             locale.currency(self._card_bal/100, grouping=True),
                                                                             locale.currency(self._cash_bal/100, grouping=True)))
        print()

    def _save_update(self, amount, bal_type, subcateg, comment, category, trans_time):
        if trans_time:
            transact_time = trans_time
        else:
            transact_time = Account._current_time()

        if bal_type == 'card':
            new_card_balance = self._card_bal + amount
            self._balance = (new_card_balance/100) + (self._cash_bal/100)

            try:
                db.execute("UPDATE accounts SET card_bal = ? WHERE (name = ?)", (new_card_balance, self.name))
                db.execute("INSERT INTO history VALUES(?, ?, ?, ?, ?, ?, ?)",
                           (transact_time, self.name, amount, category, bal_type, subcateg, comment))
            except sqlite3.Error:
                db.rollback()
            else:
                db.commit()
                self._card_bal = new_card_balance

        elif bal_type == 'cash':
            new_cash_balance = self._cash_bal + amount
            self._balance = (new_cash_balance/100) + (self._card_bal/100)

            try:
                db.execute("UPDATE accounts SET cash_bal = ? WHERE (name = ?)", (new_cash_balance, self.name))
                db.execute("INSERT INTO history VALUES(?, ?, ?, ?, ?, ?, ?)",
                           (transact_time, self.name, amount, category, bal_type, subcateg, comment))
            except sqlite3.Error:
                print("cash error")
                db.rollback()
            else:
                db.commit()
                self._cash_bal = new_cash_balance

        else:
            print("Incorrect account type entered")

    def deposit(self, amount: int, bal_type, subcateg='', comment='', trans_time=None):
        global transaction_feedback
        category = 'deposit'
        if bal_type == 'card':
            if amount > 0.0:
                self._save_update(amount, 'card', subcateg, comment, category, trans_time)
                transaction_feedback = "{:.2f} deposited to card".format(amount / 100)
                print(transaction_feedback)
            return self._card_bal / 100

        elif bal_type == 'cash':
            if amount > 0.0:
                self._save_update(amount, 'cash', subcateg, comment, category, trans_time)
                transaction_feedback = "{:.2f} deposited to cash".format(amount / 100)
                print(transaction_feedback)
            return self._cash_bal / 100

        self.show_balance()

    def expense(self, amount: int, bal_type, subcateg='', comment='', trans_time=None):
        global transaction_feedback
        category = 'expense'
        if 0 < amount <= (self._card_bal if bal_type == 'card' else self._cash_bal):
            self._save_update(-amount, bal_type, subcateg, comment, category, trans_time)
            transaction_feedback = "{:.2f} deducted from {}".format(amount / 100, 'card' if bal_type == 'card' else 'cash')
            print(transaction_feedback)
            self.show_balance()
            return amount / 100
        else:
            transaction_feedback = "The amount must be greater than zero and no more than your account balance"
            print(transaction_feedback)
            return 0.0

    def transfer(self, amount: int, from_acc, to_acc, trans_time=None):  # just internal transfer within same Account: Card to Cash
        global transfer_feedback
        # current: just amount, card, cash
        # manual: amount, card, cash, DATE
        if from_acc == 'card' and to_acc == 'cash' and trans_time is None:
            if 0 < amount <= self._card_bal:
                self._save_update(-amount, bal_type='card', subcateg='', comment='to cash', category='transfer', trans_time=trans_time)
                self._save_update(amount, bal_type='cash', subcateg='', comment='from card', category='transfer', trans_time=trans_time)
                transfer_feedback = "{:.2f} transfered from card to cash".format(amount / 100)
                print(transfer_feedback)
                return amount / 100
            else:
                transfer_feedback = "The amount must be greater than zero and no more than your account balance"
                print(transfer_feedback)
                return 0.0
        elif from_acc == 'card' and to_acc == 'cash' and trans_time:           # HERE MODIFY FOR NEW TRANS_TIME + 1 SECOND
            trans_time_2 = trans_time.replace(second=1)
            if 0 < amount <= self._card_bal:
                self._save_update(-amount, bal_type='card', subcateg='', comment='to cash', category='transfer', trans_time=trans_time)
                self._save_update(amount, bal_type='cash', subcateg='', comment='from card', category='transfer', trans_time=trans_time_2)
                transfer_feedback = "{:.2f} transfered from card to cash".format(amount / 100)
                print(transfer_feedback)
                return amount / 100
            else:
                transfer_feedback = "The amount must be greater than zero and no more than your account balance"
                print(transfer_feedback)
                return 0.0

        else:
            print("Other type of transfer attempted which is still not supported")
            return 0.0

    def display_filtered_transact(self, date_from=None, date_to=None, category=None):
        # bal_type=None, subcateg=None

        sql_select = "SELECT strftime('%Y-%m-%d %H:%M:%S', history.time, 'localtime'), history.account, " \
                     "history.category, history.amount, history.bal_type, history.subcateg, history.comment FROM history"

        sql_where = " WHERE history.account = ?"

        sql_sort = " ORDER BY history.time"

        if date_from and date_to and category:
            # category is a list
            if len(category) == 1:
                sql_where_date = " AND history.time BETWEEN ? and ?"
                sql_where_category = " AND history.category = ?"
                cursor = db.execute(sql_select + sql_where + sql_where_date + sql_where_category +
                                    sql_sort, (self.name, date_from, date_to, category[0]))
            elif len(category) == 2:
                sql_where_date = " AND history.time BETWEEN ? and ?"
                sql_where_category = " and (history.category = ? or history.category = ?)"
                cursor = db.execute(sql_select + sql_where + sql_where_date + sql_where_category +
                                    sql_sort, (self.name, date_from, date_to, category[0], category[1]))
            else:   # if len(category) == 3:
                sql_where_date = " AND history.time BETWEEN ? and ?"
                cursor = db.execute(sql_select + sql_where + sql_where_date + sql_sort, (self.name, date_from, date_to))

        elif date_from and date_to:  # same as if len(category) == 3:
            sql_where_date = " AND history.time BETWEEN ? and ?"
            cursor = db.execute(sql_select + sql_where + sql_where_date + sql_sort, (self.name, date_from, date_to))

        else:
            cursor = db.execute(sql_select + sql_where + sql_sort, (self.name,))

        all_transac = cursor.fetchall()
        return all_transac

    def summary_default(self):
        # default summary of expenses and income in current calendar month
        # returns raw INTEGER from DB

        year_month = str(datetime.datetime.now().year) + "-" + \
            ("0"+str(datetime.datetime.now().month) if len(str(datetime.datetime.now().month)) == 1 else "")

        cursor_exp = db.execute("SELECT sum(history.amount) "
                                "FROM history "
                                "WHERE history.category = 'expense' "
                                "and history.account = ? and history.time LIKE ?", (self.name, year_month+'%'))

        cursor_inc = db.execute("SELECT sum(history.amount) "
                                "FROM history "
                                "WHERE history.category = 'deposit' and "
                                "history.account = ? and history.time LIKE ?", (self.name, year_month+'%'))

        current_month_sum_expense = cursor_exp.fetchone()
        current_month_sum_deposit = cursor_inc.fetchone()

        return current_month_sum_deposit[0] if current_month_sum_deposit[0] is not None else 0, \
            current_month_sum_expense[0] if current_month_sum_expense[0] is not None else 0


class ScrollListBox(tkinter.Listbox):
    def __init__(self, window, **kwargs):
        super().__init__(window, **kwargs)
        self.scrollbar = tkinter.Scrollbar(window, orient=tkinter.VERTICAL, command=self.yview)

    def grid(self, roww, column, sticky='nswe', rowspan=1, columnspan=1, **kwargs):
        super().grid(row=roww, column=column, sticky=sticky, rowspan=rowspan, columnspan=columnspan, **kwargs)
        self.scrollbar.grid(row=roww, column=column, sticky='nse', rowspan=rowspan, columnspan=columnspan)
        self['yscrollcommand'] = self.scrollbar.set

########################################################################


# GUI FLOW & FUNCTIONS

def main_window_widgets():
    # Initiates tkinter root window (mainWindow)
    # Then creates a new frame within mainWindow ( calling external function new_frame() )
    # Initial screen for User with 2 options: CREATE or ACCESS an account
    # all widgets are created within the Frame
    # NEXT & EXIT buttons
    # sub-function: next_screen_0: handler for NEXT button
    #                    it calls external functions: create_account() or existing_Account()

    def next_screen_0():
        # NEXT button handler (within Initial window (in main_frame, within mainWindow)
        if rb_value_0.get() == 1:
            create_account()
        else:   # rb_value_0.get() == 2
            existing_account()

    main_frame.destroy()
    new_frame()
    main_frame.grid(row=2, column=2, sticky='nswe')
    # Label Frame for radio buttons
    option_frame = tkinter.LabelFrame(main_frame, text="Please choose an option: ")
    option_frame.grid(row=1, column=0, columnspan=3)

    # radio buttons control variable
    rb_value_0 = tkinter.IntVar()
    rb_value_0.set(2)      # Default value

    # radio buttons
    radio1 = tkinter.Radiobutton(option_frame, text="Create a new account", value=1, variable=rb_value_0)
    radio2 = tkinter.Radiobutton(option_frame, text="Access an existing account", value=2, variable=rb_value_0)
    radio1.grid(row=1, column=0, sticky='w')
    radio2.grid(row=2, column=0, sticky='w')

    # Initial NEXT and EXIT buttons
    next_button_0 = tkinter.Button(main_frame, text='Next', command=next_screen_0)
    next_button_0.grid(row=17, column=1, sticky='we')

    cancel_button = tkinter.Button(main_frame, text='Exit', command=mainWindow.quit)
    cancel_button.grid(row=17, column=2, sticky='we')


def new_frame():
    # to create a new Frame within root window (mainWindow)
    global main_frame
    main_frame = tkinter.Frame(mainWindow, borderwidth=2, relief='raised')

    main_frame.grid(row=2, column=3, sticky='nswe', columnspan=3, rowspan=18)
    main_frame.columnconfigure(0, weight=1000)
    main_frame.columnconfigure(1, weight=1000)
    main_frame.columnconfigure(2, weight=1000)
    main_frame.columnconfigure(3, weight=1000)  # has no effect
    main_frame.columnconfigure(4, weight=1000)  # has no effect
    for ii in range(0, 18):
        main_frame.rowconfigure(ii, weight=3)


def create_account():

    main_frame.destroy()
    new_frame()

    ent_name = tkinter.StringVar()
    ent_card = tkinter.IntVar()
    ent_cash = tkinter.IntVar()
    currency_var = tkinter.StringVar()
    currency_var.set(None)  # so it doesn't show all options as 'selected' before clicking on one of them

    def get_values():
        n = ent_name.get()
        c = ent_card.get()
        s = ent_cash.get()
        r = currency_var.get()
        return n, c, s, r

    def confirmation():
        global conf_button_1, conf_label
        n, c, s, r = get_values()
        confirmation_str = """
        Are you sure you want to create an account?
        
        Name:\t\t\t{}
        Currency:\t\t\t{}
        Opening Card Balance:\t{} 
        Opening Cash Balance:\t{}""".format(n, r, c, s)

        conf_label = tkinter.Label(main_frame, text='', justify='left', width=45)               # ## Empty for keeping size the same
        conf_label.grid(row=7, columnspan=3)                                                    # ## Empty for keeping size the same
        conf_label['text'] = confirmation_str

        continue_button_1.destroy()
        conf_button_1 = tkinter.Button(main_frame, text='Confirm', command=initialize_acc)
        conf_button_1.grid(row=14, column=3, sticky='e')

    def initialize_acc():
        global new_acc
        conf_button_1.destroy()
        back_button_1.destroy()
        conf_label.destroy()
        name_new, op_crd_bal, op_csh_bal, cur = get_values()
        new_acc = Account(name_new, cur, int(op_crd_bal * 100), int(op_csh_bal * 100))
        message_label = tkinter.Label(main_frame, text=init_message, justify='left')
        message_label.grid(row=7, rowspan=3, columnspan=3)

        next_button_1 = tkinter.Button(main_frame, text='Next', command=existing_account)
        next_button_1.grid(row=30, column=0)
        cancel_button_1 = tkinter.Button(main_frame, text='Exit', command=mainWindow.quit)
        cancel_button_1.grid(row=30, column=1)

    welcome_label = tkinter.Label(main_frame, text='Creating account:')
    welcome_label.grid(row=0, column=0, sticky='w')

    name_label = tkinter.Label(main_frame, text='Type in the name: ')
    name_label.grid(row=3, column=0, sticky='w')
    entry_name_field = tkinter.Entry(main_frame, relief='ridge', textvariable=ent_name)
    entry_name_field.grid(row=3, column=1, sticky='w')

    name_label = tkinter.Label(main_frame, text='Type in Card Balance: ')
    name_label.grid(row=4, column=0, sticky='w')
    entry_card_field = tkinter.Entry(main_frame, relief='ridge', textvariable=ent_card)
    entry_card_field.grid(row=4, column=1, sticky='w')

    name_label = tkinter.Label(main_frame, text='Type in Cash Balance: ')
    name_label.grid(row=5, column=0, sticky='w')
    entry_cash_field = tkinter.Entry(main_frame, relief='ridge', textvariable=ent_cash)
    entry_cash_field.grid(row=5, column=1, sticky='w')

    curr_option_frame = tkinter.LabelFrame(main_frame, text="Choose currency: ")
    curr_option_frame.grid(row=1, column=3, rowspan=6)

    curr_us = tkinter.Radiobutton(curr_option_frame, text="US Dollar", value='en-US', variable=currency_var)
    curr_eu = tkinter.Radiobutton(curr_option_frame, text="Euro", value='EU', variable=currency_var)
    curr_gb = tkinter.Radiobutton(curr_option_frame, text="GB Pound", value='en-GB', variable=currency_var)
    curr_mx = tkinter.Radiobutton(curr_option_frame, text="MX Peso", value='es-MX', variable=currency_var)
    curr_hr = tkinter.Radiobutton(curr_option_frame, text="HR Kuna", value='HR', variable=currency_var)

    curr_us.grid(sticky='w')   # row=0, column=0, sticky='w'
    curr_eu.grid(sticky='w')
    curr_gb.grid(sticky='w')
    curr_mx.grid(sticky='w')
    curr_hr.grid(sticky='w')

    # continue or back button
    continue_button_1 = tkinter.Button(main_frame, text='Continue', command=confirmation)
    continue_button_1.grid(row=14, column=3, sticky='e')

    back_button_1 = tkinter.Button(main_frame, text='Back', command=main_window_widgets)
    back_button_1.grid(row=14, column=3, sticky='w')


def existing_account():

    def initial_screen():
        global input_name
        main_frame.destroy()
        new_frame()
        main_frame.grid(row=2, column=2, sticky='nswe')

        input_name = tkinter.StringVar()
        input_name_label = tkinter.Label(main_frame, text='Type in the name: ')
        input_name_label.grid(row=3, column=0, sticky='e')
        input_name_entry = tkinter.Entry(main_frame, relief='ridge', textvariable=input_name)
        input_name_entry.grid(row=3, column=1, sticky='w', columnspan=2)

        # NEXT and EXIT buttons
        next_button_2_0 = tkinter.Button(main_frame, text='Next', command=retrieve_account_tk)
        next_button_2_0.grid(row=17, column=1, sticky='we')

        cancel_button_2_0 = tkinter.Button(main_frame, text='Exit', command=mainWindow.quit)
        cancel_button_2_0.grid(row=17, column=2, sticky='we')

    def retrieve_account_tk():
        global name_2, row
        name_2 = input_name.get()
        row = Account.retrieve_account(name_2)

        if row:
            main_frame.destroy()
            new_frame()
            working_screen()
        else:
            # if the account does not exist: "Account not found"
            not_found_label = tkinter.Label(main_frame, text="Account not found\n\nPlease re-enter the name")
            not_found_label.grid(row=5, column=1, sticky='w')

    def create_balance_3widgets():
        global existing_account_var, existing_account_label, total_bal_label, card_cash_bal_text, card_cash_bal_label
        existing_account_var = Account(name_2, '')
        existing_account_label = tkinter.Label(main_frame, text=row[0]+':')
        existing_account_label.grid(row=0, column=0, sticky='w')

        total_bal_label = tkinter.Label(main_frame, text=locale.currency(existing_account_var._balance, grouping=True))
        total_bal_label.grid(row=0, column=1, sticky='we')
        card_cash_bal_text = "(Card: {} + Cash: {})".format(
            locale.currency(existing_account_var._card_bal/100, symbol=False, grouping=True),
            locale.currency(existing_account_var._cash_bal/100, symbol=False, grouping=True))
        card_cash_bal_label = tkinter.Label(main_frame, text=card_cash_bal_text)
        card_cash_bal_label.grid(row=0, column=2, sticky='we', columnspan=3)

    def destroy_balance_3widgets():
        existing_account_label.destroy()
        total_bal_label.destroy()
        card_cash_bal_label.destroy()
        pass

    def summary_default_widgets():
        dep_exp_list = existing_account_var.summary_default()   # should return (sum_deposit, sum_expense) of current month (integer not divided by 100)
        summary_frame = tkinter.Frame(main_frame)
        summary_frame.grid(row=1, column=0, columnspan=3, sticky='w')

        tkinter.Label(summary_frame, text="Current month Summary: ", font=("Arial", 14)).grid(row=1, column=0, sticky='w')
        month = str(datetime.datetime.now().year) + " - " + \
            ("0"+str(datetime.datetime.now().month) if len(str(datetime.datetime.now().month)) == 1 else "")
        tkinter.Label(summary_frame, text=month, font=("Arial", 14)).grid(row=1, column=1, sticky='w')

        tkinter.Label(summary_frame, text="Deposits: ", font=("Arial", 10)).grid(row=3, column=0, sticky='w')
        tkinter.Label(summary_frame, text=locale.currency(dep_exp_list[0]/100, grouping=True),
                      font=("Arial", 10)).grid(row=3, column=1, sticky='w')

        tkinter.Label(summary_frame, text="Expenses: ", font=("Arial", 10)).grid(row=4, column=0, sticky='w')
        tkinter.Label(summary_frame, text=locale.currency(dep_exp_list[1]/100, grouping=True),
                      font=("Arial", 10)).grid(row=4, column=1, sticky='w')

    def working_screen():   # EMPTY (just 3 items: Name, Total Bal, card+cash bal) + 7 root buttons

        def go_back_7():
            # 'BACK' button handler
            initial_screen()
            destroy_trans_btns()

        def destroy_trans_btns():
            # destroy transaction and Exit buttons in root(mainWindow)
            # btn1_show_bal.destroy()
            btn2_n_expens.destroy()
            btn3_n_income.destroy()
            btn4_transfer.destroy()
            # btn5_f_transa.destroy()
            btn6_a_transa.destroy()
            btn7_go_back.destroy()
            cancel_button_2_1.destroy()

        # SHOW 'NAME' OF CURRENT ACCOUNT, AND CURRENT BALANCE (top of new_frame)
        create_balance_3widgets()

        summary_default_widgets()

        # TRANSACTION BUTTONS in root window (LEFT SIDE)
        # btn1_show_bal = tkinter.Button(mainWindow, text="Show/Hide Balance", command=show_bal_btn_handler)
        btn2_n_expens = tkinter.Button(mainWindow, text="New Expense", command=new_exp_btn_handler)
        btn3_n_income = tkinter.Button(mainWindow, text="New Income", command=new_inc_btn_handler)
        btn4_transfer = tkinter.Button(mainWindow, text="New Transfer", command=new_transfer_btn_handler)
        # btn5_f_transa = tkinter.Button(mainWindow, text="Filter Transactions")
        btn6_a_transa = tkinter.Button(mainWindow, text="All Transactions", command=all_trnscts_btn_handler)
        btn7_go_back = tkinter.Button(mainWindow, text="Back", command=go_back_7)

        # btn1_show_bal.grid(row=4, column=1, sticky='we')
        btn2_n_expens.grid(row=5, column=1, sticky='we')
        btn3_n_income.grid(row=6, column=1, sticky='we')
        btn4_transfer.grid(row=7, column=1, sticky='we')
        # btn5_f_transa.grid(row=8, column=1, sticky='we')
        btn6_a_transa.grid(row=9, column=1, sticky='we')
        btn7_go_back.grid(row=12, column=1, sticky='we')

        # EXIT button (root Bottom)
        cancel_button_2_1 = tkinter.Button(mainWindow, text='Exit', command=mainWindow.quit)
        cancel_button_2_1.grid(row=13, column=1, sticky='we')

    def show_bal_btn_handler():
        if existing_account_label:
            destroy_balance_3widgets()
        else:
            create_balance_3widgets()
        pass

    def new_exp_btn_handler():
        global trans_type
        trans_type = 'expense'
        new_transaction()

    def new_inc_btn_handler():
        global trans_type
        trans_type = 'income'
        new_transaction()

    def new_transfer_btn_handler():
        global trans_type
        trans_type = 'transfer'
        new_transfer()

    def all_trnscts_btn_handler():
        global trans_type
        trans_type = 'All Transactions'
        all_trnscts()

    def new_transaction():
        global total_bal_label

        def create_all_new_transact_widgets():
            global transact_type_label, new_amount_label, new_amount_input, new_baltype_label, new_subcateg_label, \
                new_subcateg_input, new_baltype_rb1, new_baltype_rb2, new_comm_label, new_comm_input, time_frame, transfer_save_btn, new_amount_var, new_subcateg_var, new_comm_var, new_baltype_var, date_select_rb_var
            global year_spin_var, month_spin_var, day_spin_var, hour_spin_var, minute_spin_var
            # 12 widgets created

            # Label for type of transaction: Expense or Income
            transact_type_label_text = 'New Income' if trans_type == 'income' else 'New Expense'
            transact_type_label = tkinter.Label(main_frame, text=transact_type_label_text, font=("Arial", 12))
            transact_type_label.grid(row=1, column=0, sticky='nw')

            # Input Amount (Label & Entry)
            new_amount_var = tkinter.DoubleVar()
            new_amount_var.set(0)
            new_amount_label = tkinter.Label(main_frame, text="Type in the amount: ")
            new_amount_input = tkinter.Entry(main_frame, textvariable=new_amount_var)
            new_amount_label.grid(row=2, column=0, sticky='w')
            new_amount_input.grid(row=2, column=1)

            # Way of payment "cash or card" (Label & Radio buttons)
            new_baltype_var = tkinter.StringVar()
            new_baltype_var.set('card')
            new_baltype_label = tkinter.Label(main_frame, text="Choose way of payment: ")
            new_baltype_rb1 = tkinter.Radiobutton(main_frame, text="Card", value='card', variable=new_baltype_var)
            new_baltype_rb2 = tkinter.Radiobutton(main_frame, text="Cash", value='cash', variable=new_baltype_var)
            new_baltype_label.grid(row=3, column=0, sticky='w')
            new_baltype_rb1.grid(row=3, column=1, sticky='w', padx=5)
            new_baltype_rb2.grid(row=3, column=1, sticky='e', padx=5)

            # exp_subcateg = input("Expense category (Food, House, Health, Entertainment,etc.): ")
            # inc_subcateg = input("Income category (Salary, Savings, Other, etc.): ")
            new_subcateg_var = tkinter.StringVar()
            new_subcateg_var.set('')
            new_subcateg_label = tkinter.Label(main_frame, text="Type in the Subcategory: ")
            new_subcateg_input = tkinter.Entry(main_frame, textvariable=new_subcateg_var)
            new_subcateg_label.grid(row=4, column=0, sticky='w')
            new_subcateg_input.grid(row=4, column=1)

            # comment = input("Comment")
            new_comm_var = tkinter.StringVar()
            new_comm_var.set('')
            new_comm_label = tkinter.Label(main_frame, text="Type in a comment: ")
            new_comm_input = tkinter.Entry(main_frame, textvariable=new_comm_var)
            new_comm_label.grid(row=5, column=0, sticky='w')
            new_comm_input.grid(row=5, column=1)

            # FRAME for the Date & Time Spinners
            time_frame = tkinter.LabelFrame(main_frame)
            time_frame.grid(row=6, column=1, columnspan=2, sticky='w')

            # Radio Buttons to select current date/time or another date/time
            date_select_rb_var = tkinter.StringVar()
            date_select_rb_var.set('current')
            current_time_rb = tkinter.Radiobutton(time_frame, text="Current date", value='current', variable=date_select_rb_var)
            manual_time_rb = tkinter.Radiobutton(time_frame, text="Manual date", value='manual', variable=date_select_rb_var)
            current_time_rb.grid(row=1, column=4)
            manual_time_rb.grid(row=2, column=4)

            # date labels
            day_label = tkinter.Label(time_frame, text="Day")
            month_label = tkinter.Label(time_frame, text="Month")
            year_label = tkinter.Label(time_frame, text="Year")
            day_label.grid(row=0, column=0, sticky='w')
            month_label.grid(row=0, column=1, sticky='w')
            year_label.grid(row=0, column=2, sticky='w')

            # date spinners
            year_spin_var = tkinter.IntVar()
            month_spin_var = tkinter.IntVar()
            day_spin_var = tkinter.IntVar()

            dt_now = datetime.datetime.now()

            year_spin_var.set(dt_now.year)
            month_spin_var.set(dt_now.month)
            day_spin_var.set(dt_now.day)

            day_spin = tkinter.Spinbox(time_frame, width=5, from_=1, to=31, textvariable=day_spin_var)
            month_spin = tkinter.Spinbox(time_frame, width=5, from_=1, to=12, textvariable=month_spin_var)
            year_spin = tkinter.Spinbox(time_frame, width=5, from_=2000, to=2099, textvariable=year_spin_var)
            day_spin.grid(row=1, column=0)
            month_spin.grid(row=1, column=1)
            year_spin.grid(row=1, column=2)

            # time spinners
            hour_spin_var = tkinter.IntVar()
            minute_spin_var = tkinter.IntVar()

            hour_spin_var.set(dt_now.hour)
            minute_spin_var.set(dt_now.minute)

            hour_spin = tkinter.Spinbox(time_frame, width=3, from_=0, to=23, textvariable=hour_spin_var)
            minute_spin = tkinter.Spinbox(time_frame, width=3, from_=0, to=59, textvariable=minute_spin_var)
            hour_spin.grid(row=2, column=0, sticky='e')
            tkinter.Label(time_frame, text=":").grid(row=2, column=1)
            minute_spin.grid(row=2, column=2, sticky='w')
            # time_frame['padx'] = 40

            # SAVE BUTTON
            transfer_save_btn = tkinter.Button(main_frame, text='Save', command=new_transact_save_btn_handler)
            transfer_save_btn.grid(row=7, column=0)

        def clear_all_new_transact_widgets():
            # 12 widgets to destroy
            transact_type_label.destroy()
            new_amount_label.destroy()
            new_amount_input.destroy()

            new_baltype_label.destroy()
            new_baltype_rb1.destroy()
            new_baltype_rb2.destroy()

            new_subcateg_label.destroy()
            new_subcateg_input.destroy()

            new_comm_label.destroy()
            new_comm_input.destroy()
            time_frame.destroy()
            transfer_save_btn.destroy()

        def new_transact_save_btn_handler():
            global feedback_label, card_cash_bal_text

            amount = new_amount_var.get()
            subcateg = new_subcateg_var.get()
            comment = new_comm_var.get()
            bal_type = new_baltype_var.get()

            dt_cur_or_man = date_select_rb_var.get()
            if dt_cur_or_man == 'current':
                if trans_type == 'expense':
                    existing_account_var.expense(int(amount*100), bal_type, subcateg, comment)
                else:   # if 'income'
                    existing_account_var.deposit(int(amount*100), bal_type, subcateg, comment)
            else:     # if 'manual'
                x_year = year_spin_var.get()
                x_month = month_spin_var.get()
                x_day = day_spin_var.get()
                x_hour = hour_spin_var.get()
                x_minute = minute_spin_var.get()

                local_tz_long = tzlocal.get_localzone()
                local_tz_short = pytz.timezone(datetime.datetime.now(local_tz_long).tzname())  # to work with REPLACE tzinfo
                manual_dt = datetime.datetime(x_year, x_month, x_day, x_hour, x_minute, 0, 0)
                manual_dt_plus_tz = manual_dt.replace(tzinfo=local_tz_short)

                manual_dt_in_utc = manual_dt_plus_tz.astimezone(pytz.utc)

                if trans_type == 'expense':
                    existing_account_var.expense(int(amount*100), bal_type, subcateg, comment, manual_dt_in_utc)
                else:   # if 'income'
                    existing_account_var.deposit(int(amount*100), bal_type, subcateg, comment, manual_dt_in_utc)

            clear_all_new_transact_widgets()

            # FEEDBACK LABEL
            feedback_label = tkinter.Label(main_frame, relief='groove', text=transaction_feedback)
            feedback_label.grid(row=3, column=0, columnspan=3, sticky='w')

            total_bal_label['text'] = locale.currency(existing_account_var._balance, grouping=True)
            card_cash_bal_text = "(Card: {} + Cash: {})".format(
                locale.currency(existing_account_var._card_bal/100, grouping=True),
                locale.currency(existing_account_var._cash_bal/100, grouping=True))
            card_cash_bal_label['text'] = card_cash_bal_text

        # CREATE ALL WIDGETS TO ENTER A NEW TRANSACTION
        main_frame.destroy()
        new_frame()
        create_balance_3widgets()
        create_all_new_transact_widgets()

    def new_transfer():
        global total_bal_label

        def create_all_new_transfer_widgets():
            global transact_type_label, new_amount_label, new_amount_input, time_frame, transfer_save_btn   # widgets
            global new_amount_var, date_select_rb_var                                                       # control variables
            global year_spin_var, month_spin_var, day_spin_var, hour_spin_var, minute_spin_var              # date control variables

            # Label for type of transaction: New Transfer
            transact_type_label_text = 'New Transfer' if trans_type == 'transfer' else 'ERROR'
            transact_type_label = tkinter.Label(main_frame, text=transact_type_label_text, font=("Arial", 12))
            transact_type_label.grid(row=1, column=0, sticky='nw')

            # Input Amount (Label & Entry)
            new_amount_var = tkinter.DoubleVar()
            new_amount_var.set(0)
            new_amount_label = tkinter.Label(main_frame, text="Type in the amount: ")
            new_amount_input = tkinter.Entry(main_frame, textvariable=new_amount_var)
            new_amount_label.grid(row=2, column=0, sticky='w')
            new_amount_input.grid(row=2, column=1)

            # FRAME for the Date & Time Spinners
            time_frame = tkinter.LabelFrame(main_frame)
            time_frame.grid(row=6, column=1, columnspan=2, sticky='w')

            # Radio Buttons to select current date/time or another date/time (in TIME_FRAME)
            date_select_rb_var = tkinter.StringVar()
            date_select_rb_var.set('current')
            current_time_rb = tkinter.Radiobutton(time_frame, text="Current date", value='current', variable=date_select_rb_var)
            manual_time_rb = tkinter.Radiobutton(time_frame, text="Manual date", value='manual', variable=date_select_rb_var)
            current_time_rb.grid(row=1, column=4)
            manual_time_rb.grid(row=2, column=4)

            # date labels  (in TIME_FRAME)
            day_label = tkinter.Label(time_frame, text="Day")
            month_label = tkinter.Label(time_frame, text="Month")
            year_label = tkinter.Label(time_frame, text="Year")
            day_label.grid(row=0, column=0, sticky='w')
            month_label.grid(row=0, column=1, sticky='w')
            year_label.grid(row=0, column=2, sticky='w')

            # date spinners  (in TIME_FRAME)
            year_spin_var = tkinter.IntVar()
            month_spin_var = tkinter.IntVar()
            day_spin_var = tkinter.IntVar()

            dt_now = datetime.datetime.now()

            year_spin_var.set(dt_now.year)
            month_spin_var.set(dt_now.month)
            day_spin_var.set(dt_now.day)

            day_spin = tkinter.Spinbox(time_frame, width=5, from_=1, to=31, textvariable=day_spin_var)
            month_spin = tkinter.Spinbox(time_frame, width=5, from_=1, to=12, textvariable=month_spin_var)
            year_spin = tkinter.Spinbox(time_frame, width=5, from_=2000, to=2099, textvariable=year_spin_var)
            day_spin.grid(row=1, column=0)
            month_spin.grid(row=1, column=1)
            year_spin.grid(row=1, column=2)

            # time spinners  (in TIME_FRAME)
            hour_spin_var = tkinter.IntVar()
            minute_spin_var = tkinter.IntVar()

            hour_spin_var.set(dt_now.hour)
            minute_spin_var.set(dt_now.minute)

            hour_spin = tkinter.Spinbox(time_frame, width=3, from_=0, to=23, textvariable=hour_spin_var)
            minute_spin = tkinter.Spinbox(time_frame, width=3, from_=0, to=59, textvariable=minute_spin_var)
            hour_spin.grid(row=2, column=0, sticky='e')
            tkinter.Label(time_frame, text=":").grid(row=2, column=1)
            minute_spin.grid(row=2, column=2, sticky='w')
            # time_frame['padx'] = 40

            # SAVE BUTTON
            transfer_save_btn = tkinter.Button(main_frame, text='Save', command=new_transfer_save_btn_handler)
            transfer_save_btn.grid(row=7, column=0)

        def clear_all_new_transfer_widgets():
            transact_type_label.destroy()
            new_amount_label.destroy()
            new_amount_input.destroy()
            time_frame.destroy()
            transfer_save_btn.destroy()

        def new_transfer_save_btn_handler():
            global total_bal_label, feedback_label, card_cash_bal_text

            amount = new_amount_var.get()

            dt_cur_or_man = date_select_rb_var.get()
            if dt_cur_or_man == 'current':
                    existing_account_var.transfer(int(amount*100), 'card', 'cash')
            else:     # if 'manual'
                x_year = year_spin_var.get()
                x_month = month_spin_var.get()
                x_day = day_spin_var.get()
                x_hour = hour_spin_var.get()
                x_minute = minute_spin_var.get()

                local_tz_long = tzlocal.get_localzone()
                local_tz_short = pytz.timezone(datetime.datetime.now(local_tz_long).tzname())  # to work with REPLACE tzinfo
                manual_dt = datetime.datetime(x_year, x_month, x_day, x_hour, x_minute, 0, 0)
                manual_dt_plus_tz = manual_dt.replace(tzinfo=local_tz_short)

                manual_dt_in_utc = manual_dt_plus_tz.astimezone(pytz.utc)

                existing_account_var.transfer(int(amount*100), 'card', 'cash', manual_dt_in_utc)

            clear_all_new_transfer_widgets()

            # FEEDBACK LABEL
            feedback_label = tkinter.Label(main_frame, relief='groove', text=transfer_feedback)
            feedback_label.grid(row=3, column=0, columnspan=3, sticky='w')

            total_bal_label['text'] = locale.currency(existing_account_var._balance, grouping=True)
            card_cash_bal_text = "(Card: {} + Cash: {})".format(
                locale.currency(existing_account_var._card_bal/100, grouping=True),
                locale.currency(existing_account_var._cash_bal/100, grouping=True))
            card_cash_bal_label['text'] = card_cash_bal_text

        main_frame.destroy()
        new_frame()
        create_balance_3widgets()
        create_all_new_transfer_widgets()

    def all_trnscts():

        def treeview_box():
            global trnsctns_box_tree
            # create box to display transactions (ttk Treeview)
            main_label = tkinter.Label(main_frame, text="All Transactions", font=("Arial", 10))
            main_label.grid(row=1, column=0, columnspan=3)

            # create Treeview
            cols = ('Date', 'Category', 'Amount', 'Type', 'Subcategory', 'Comments')
            trnsctns_box_tree = tkinter.ttk.Treeview(main_frame, columns=cols, show='headings')
            trnsctns_box_tree.grid(row=2, column=0, columnspan=3, sticky='w', padx=20)

            trnsctns_box_tree.column('Date', width=130)
            trnsctns_box_tree.column('Category', width=80)
            trnsctns_box_tree.column('Amount', width=80, anchor='e')
            trnsctns_box_tree.column('Type', width=50, anchor='center')
            trnsctns_box_tree.column('Subcategory', width=100)
            trnsctns_box_tree.column('Comments', width=130)

            # set column headings
            for col in cols:
                trnsctns_box_tree.heading(col, text=col)

        def filter_widgets():

            def get_filter_values():

                index = category_filter_lb.curselection()
                print("index: ", index)
                category_selected_list = []     # strings
                for num in range(len(index)):
                    category_selected = category_filter_lb.get(index[num])
                    category_selected_list.append(category_selected.lower())

                from_date_list = [
                    year_spin_var.get(),
                    month_spin_var.get(),
                    day_spin_var.get(),
                    hour_spin_var.get(),
                    minute_spin_var.get()]

                from_date_dt = datetime.datetime(year_spin_var.get(), month_spin_var.get(), day_spin_var.get())
                from_date_str = from_date_dt.strftime("%Y-%m-%d")

                to_date_list = [
                    year_spin_var_to.get(),
                    month_spin_var_to.get(),
                    day_spin_var_to.get(),
                    hour_spin_var_to.get(),
                    minute_spin_var_to.get()]

                to_date_dt = datetime.datetime(year_spin_var_to.get(), month_spin_var_to.get(), day_spin_var_to.get()+1)
                to_date_str = to_date_dt.strftime("%Y-%m-%d")

                return from_date_str, to_date_str, category_selected_list

            # Filter Button
            def filter_btn_handler():
                from_filter, to_filter, categ_filter = get_filter_values()

                trnsctns_box_tree.delete(*trnsctns_box_tree.get_children())
                # insert the filtered values in display box
                # HERE CALL instance method, which returns all_transact that apply

                filtered_trnscts = existing_account_var.display_filtered_transact(from_filter, to_filter, categ_filter)

                for item, (dt, account, category, amount, baltype, subcateg, comment) in enumerate(filtered_trnscts, start=1):
                    trnsctns_box_tree.insert("", "end", values=(dt, category, locale.currency(amount/100, symbol=False, grouping=True), baltype, subcateg, comment))

            # FILTER Button
            re_filter = tkinter.Button(main_frame, text='Filter', command=filter_btn_handler)
            re_filter.grid(row=6, column=1, sticky='e')

            # DATE/TIME LabelFrame FROM
            time_frame_from = tkinter.LabelFrame(main_frame, text='From:')
            time_frame_from.grid(row=4, column=0, columnspan=1, sticky='w', padx='20')

            # DATE LABELS From
            day_label = tkinter.Label(time_frame_from, text="dd")
            month_label = tkinter.Label(time_frame_from, text="mm")
            year_label = tkinter.Label(time_frame_from, text="yyyy")
            day_label.grid(row=0, column=0, sticky='w')
            month_label.grid(row=0, column=1, sticky='w')
            year_label.grid(row=0, column=2, sticky='w')

            # DATE SPINNERS From
            year_spin_var = tkinter.IntVar()
            month_spin_var = tkinter.IntVar()
            day_spin_var = tkinter.IntVar()

            dt_now = datetime.datetime.now()

            year_spin_var.set(dt_now.year)
            month_spin_var.set(dt_now.month)
            day_spin_var.set(dt_now.day)

            day_spin = tkinter.Spinbox(time_frame_from, width=3, from_=1, to=31, textvariable=day_spin_var)
            month_spin = tkinter.Spinbox(time_frame_from, width=3, from_=1, to=12, textvariable=month_spin_var)
            year_spin = tkinter.Spinbox(time_frame_from, width=5, from_=2000, to=2099, textvariable=year_spin_var)
            day_spin.grid(row=1, column=0)
            month_spin.grid(row=1, column=1)
            year_spin.grid(row=1, column=2)

            # TIME SPINNERS From
            hour_spin_var = tkinter.IntVar()
            minute_spin_var = tkinter.IntVar()

            hour_spin_var.set(dt_now.hour)
            minute_spin_var.set(dt_now.minute)

            hour_spin = tkinter.Spinbox(time_frame_from, width=3, from_=0, to=23, textvariable=hour_spin_var)
            minute_spin = tkinter.Spinbox(time_frame_from, width=3, from_=0, to=59, textvariable=minute_spin_var)
            hour_spin.grid(row=2, column=0, sticky='w')
            tkinter.Label(time_frame_from, text=":").grid(row=2, column=0, sticky='e')
            minute_spin.grid(row=2, column=1, sticky='w')

            # DATE/TIME LabelFrame TO
            time_frame_to = tkinter.LabelFrame(main_frame, text='To:')
            time_frame_to.grid(row=5, column=0, columnspan=1, sticky='w', padx='20')

            # DATE LABELS To
            day_label = tkinter.Label(time_frame_to, text="dd")
            month_label = tkinter.Label(time_frame_to, text="mm")
            year_label = tkinter.Label(time_frame_to, text="yyyy")
            day_label.grid(row=0, column=0, sticky='w')
            month_label.grid(row=0, column=1, sticky='w')
            year_label.grid(row=0, column=2, sticky='w')

            # DATE SPINNERS To
            year_spin_var_to = tkinter.IntVar()
            month_spin_var_to = tkinter.IntVar()
            day_spin_var_to = tkinter.IntVar()

            dt_now = datetime.datetime.now()

            year_spin_var_to.set(dt_now.year)
            month_spin_var_to.set(dt_now.month)
            day_spin_var_to.set(dt_now.day)

            day_spin = tkinter.Spinbox(time_frame_to, width=3, from_=1, to=31, textvariable=day_spin_var_to)
            month_spin = tkinter.Spinbox(time_frame_to, width=3, from_=1, to=12, textvariable=month_spin_var_to)
            year_spin = tkinter.Spinbox(time_frame_to, width=5, from_=2000, to=2099, textvariable=year_spin_var_to)
            day_spin.grid(row=1, column=0)
            month_spin.grid(row=1, column=1)
            year_spin.grid(row=1, column=2)

            # TIME SPINNERS To
            hour_spin_var_to = tkinter.IntVar()
            minute_spin_var_to = tkinter.IntVar()

            hour_spin_var_to.set(dt_now.hour)
            minute_spin_var_to.set(dt_now.minute)

            hour_spin = tkinter.Spinbox(time_frame_to, width=3, from_=0, to=23, textvariable=hour_spin_var_to)
            minute_spin = tkinter.Spinbox(time_frame_to, width=3, from_=0, to=59, textvariable=minute_spin_var_to)
            hour_spin.grid(row=2, column=0, sticky='w')
            tkinter.Label(time_frame_to, text=":").grid(row=2, column=0, sticky='e')
            minute_spin.grid(row=2, column=1, sticky='w')

            # FRAME FOR CATEGORY FILTERS
            category_filter_frame = tkinter.LabelFrame(main_frame, text='Category:')
            category_filter_frame.grid(row=4, column=0, columnspan=1, rowspan=2, sticky='e')
            category_var_lb = tkinter.StringVar()
            category_filter_lb = tkinter.Listbox(category_filter_frame, selectmode=tkinter.MULTIPLE, width=8, listvariable=category_var_lb)
            category_filter_lb.grid()
            category_list = ['Expense', 'Deposit', 'Transfer']
            for cat in category_list:
                category_filter_lb.insert(tkinter.END, cat)

        def insert_all_transactions():
            # insert the values in display box
            all_trnscts_list = existing_account_var.display_all_transac()
            for ite, (dt, account, category, amount, baltype, subcateg, comment) in enumerate(all_trnscts_list, start=1):
                trnsctns_box_tree.insert("", "end", values=(dt, category, locale.currency(amount/100, symbol=False, grouping=True), baltype, subcateg, comment))

        main_frame.destroy()
        new_frame()
        create_balance_3widgets()

        treeview_box()
        filter_widgets()
        insert_all_transactions()

    initial_screen()


# ########################################### INITIALIZE ROOT

mainWindow = tkinter.Tk()
mainWindow.title('My Personal Finance App')
# mainWindow.geometry('640x480')
mainWindow.geometry('800x600')
mainWindow.columnconfigure(0, weight=1000)
mainWindow.columnconfigure(1, weight=1000)
mainWindow.columnconfigure(2, weight=1000)
mainWindow.columnconfigure(3, weight=1000)
mainWindow.columnconfigure(4, weight=1000)
mainWindow.columnconfigure(5, weight=1000)
mainWindow.columnconfigure(6, weight=1000)
for i in range(0, 22):
    mainWindow.rowconfigure(i, weight=3)

new_frame()

main_window_widgets()

mainWindow.mainloop()

db.close()
