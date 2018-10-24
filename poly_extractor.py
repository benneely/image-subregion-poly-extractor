import tkinter as tk
import ttkthemes as themed_tk
from tkinter import filedialog, ttk
import PIL.Image
import PIL.ImageTk
import os
import json
from collections import OrderedDict
import numpy as np
# weird import style to un-confuse PyCharm
try:
    from cv2 import cv2
except ImportError:
    import cv2

BACKGROUND_COLOR = '#ededed'
BORDER_COLOR = '#bebebe'
HIGHLIGHT_COLOR = '#5294e2'
ROW_ALT_COLOR = '#f3f6fa'

HANDLE_RADIUS = 4  # not really a radius, just half a side length

WINDOW_WIDTH = 890
WINDOW_HEIGHT = 720

PAD_SMALL = 2
PAD_MEDIUM = 4


class Application(tk.Frame):

    def __init__(self, master):

        tk.Frame.__init__(self, master=master)

        self.img_region_lut = None
        self.region_label_set = None
        self.base_dir = None
        self.image_dims = None
        self.current_img = None
        self.current_reg_idx = None
        self.tk_image = None
        self.new_label_var = tk.StringVar(self.master)

        self.master.minsize(width=WINDOW_WIDTH, height=WINDOW_HEIGHT)
        self.master.config(bg=BACKGROUND_COLOR)
        self.master.title("Segmentation Editor")

        main_frame = tk.Frame(self.master, bg=BACKGROUND_COLOR)
        main_frame.pack(
            fill='both',
            expand=True,
            anchor='n',
            padx=PAD_MEDIUM,
            pady=PAD_MEDIUM
        )

        file_chooser_frame = tk.Frame(main_frame, bg=BACKGROUND_COLOR)
        file_chooser_frame.pack(
            fill=tk.X,
            expand=False,
            anchor=tk.N,
            padx=PAD_MEDIUM,
            pady=PAD_MEDIUM
        )

        bottom_frame = tk.Frame(main_frame, bg=BACKGROUND_COLOR)
        bottom_frame.pack(
            fill='both',
            expand=True,
            anchor='n',
            padx=PAD_MEDIUM,
            pady=PAD_SMALL
        )

        file_chooser_button_frame = tk.Frame(
            file_chooser_frame,
            bg=BACKGROUND_COLOR
        )

        file_chooser_button = ttk.Button(
            file_chooser_button_frame,
            text='Import Regions JSON',
            command=self.choose_files
        )
        file_chooser_button.pack(side=tk.LEFT)
        add_image_button = ttk.Button(
            file_chooser_button_frame,
            text='Add Image',
            command=self.choose_new_img_file
        )
        add_image_button.pack(side=tk.LEFT)

        save_regions_button = ttk.Button(
            file_chooser_button_frame,
            text='Save Regions JSON',
            command=self.save_regions_json
        )
        save_regions_button.pack(side=tk.RIGHT, anchor=tk.N)

        delete_region_button = ttk.Button(
            file_chooser_button_frame,
            text='Delete Region',
            command=self.delete_region
        )
        delete_region_button.pack(side=tk.RIGHT, anchor=tk.N)

        add_region_button = ttk.Button(
            file_chooser_button_frame,
            text='Add Region',
            command=self.new_region
        )
        add_region_button.pack(side=tk.RIGHT, anchor=tk.N)

        new_label_button = ttk.Button(
            file_chooser_button_frame,
            text='Create New Label',
            command=self.new_label
        )
        new_label_button.pack(side=tk.RIGHT, anchor=tk.N)

        file_chooser_button_frame.pack(
            anchor='n',
            fill='x',
            expand=False,
            padx=PAD_MEDIUM,
            pady=PAD_MEDIUM
        )

        file_list_frame = tk.Frame(
            file_chooser_frame,
            bg=BACKGROUND_COLOR,
            highlightcolor=HIGHLIGHT_COLOR,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1
        )
        file_scroll_bar = ttk.Scrollbar(file_list_frame, orient='vertical')
        self.file_list_box = tk.Listbox(
            file_list_frame,
            exportselection=False,
            height=4,
            yscrollcommand=file_scroll_bar.set,
            relief='flat',
            borderwidth=0,
            highlightthickness=0,
            selectbackground=HIGHLIGHT_COLOR,
            selectforeground='#ffffff'
        )
        self.file_list_box.bind('<<ListboxSelect>>', self.select_file)
        file_scroll_bar.config(command=self.file_list_box.yview)
        file_scroll_bar.pack(side='right', fill='y')
        self.file_list_box.pack(fill='x', expand=True)

        file_list_frame.pack(
            fill='x',
            expand=False,
            padx=PAD_MEDIUM,
            pady=PAD_SMALL
        )

        region_list_frame = tk.Frame(
            bottom_frame,
            bg=BACKGROUND_COLOR,
            highlightcolor=HIGHLIGHT_COLOR,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1
        )
        region_list_frame.pack(
            fill=tk.Y,
            expand=False,
            anchor=tk.N,
            side='left',
            padx=PAD_MEDIUM,
            pady=PAD_MEDIUM
        )

        self.current_label = tk.StringVar(self.master)

        self.label_option = ttk.Combobox(
            region_list_frame,
            textvariable=self.current_label,
            state='readonly'
        )
        self.label_option.bind('<<ComboboxSelected>>', self.select_label)
        self.label_option.pack(fill='x', expand=False)

        region_scroll_bar = ttk.Scrollbar(region_list_frame, orient='vertical')
        self.region_list_box = tk.Listbox(
            region_list_frame,
            width=32,
            yscrollcommand=region_scroll_bar.set,
            relief='flat',
            borderwidth=0,
            highlightthickness=0,
            selectbackground=HIGHLIGHT_COLOR,
            selectforeground='#ffffff'
        )
        self.region_list_box.bind('<<ListboxSelect>>', self.select_region)
        region_scroll_bar.config(command=self.region_list_box.yview)
        region_scroll_bar.pack(side='right', fill='y')
        self.region_list_box.pack(fill='both', expand=True)
        
        # the canvas frame's contents will use grid b/c of the double
        # scrollbar (they don't look right using pack), but the canvas itself
        # will be packed in its frame
        canvas_frame = tk.Frame(bottom_frame, bg=BACKGROUND_COLOR)
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        canvas_frame.pack(
            fill=tk.BOTH,
            expand=True,
            anchor=tk.N,
            side='right',
            padx=PAD_MEDIUM,
            pady=PAD_MEDIUM
        )

        self.canvas = tk.Canvas(
            canvas_frame,
            cursor="tcross",
            takefocus=1
        )

        self.scrollbar_v = ttk.Scrollbar(
            canvas_frame,
            orient=tk.VERTICAL
        )
        self.scrollbar_h = ttk.Scrollbar(
            canvas_frame,
            orient=tk.HORIZONTAL
        )
        self.scrollbar_v.config(command=self.canvas.yview)
        self.scrollbar_h.config(command=self.canvas.xview)

        self.canvas.config(yscrollcommand=self.scrollbar_v.set)
        self.canvas.config(xscrollcommand=self.scrollbar_h.set)

        self.canvas.grid(
            row=0,
            column=0,
            sticky=tk.N + tk.S + tk.E + tk.W
        )
        self.scrollbar_v.grid(row=0, column=1, sticky=tk.N + tk.S)
        self.scrollbar_h.grid(row=1, column=0, sticky=tk.E + tk.W)

        # setup some button and key bindings
        self.canvas.bind("<ButtonPress-1>", self.grab_handle)
        self.canvas.bind("<B1-Motion>", self.move_handle)
        self.canvas.bind("<ButtonRelease-1>", self.release_handle)

        self.canvas.bind("<ButtonPress-2>", self.on_pan_button_press)
        self.canvas.bind("<B2-Motion>", self.pan_image)
        self.canvas.bind("<ButtonRelease-2>", self.on_pan_button_release)

        # save our sub-region snippet
        self.master.bind("<p>", self.draw_point)

        self.points = OrderedDict()
        self.selected_handle = None

        self.start_x = None
        self.start_y = None

        self.pan_start_x = None
        self.pan_start_y = None

        self.pack()

    def draw_point(self, event, override_focus=False):
        # don't do anything unless the canvas has focus
        if not isinstance(self.focus_get(), tk.Canvas) and not override_focus:
            return

        if not override_focus:
            cur_x = self.canvas.canvasx(event.x)
            cur_y = self.canvas.canvasy(event.y)
        else:
            cur_x = event.x
            cur_y = event.y

        r = self.canvas.create_rectangle(
            cur_x - HANDLE_RADIUS,
            cur_y - HANDLE_RADIUS,
            cur_x + HANDLE_RADIUS,
            cur_y + HANDLE_RADIUS,
            outline='#00ff00',
            width=2,
            tags='handle'
        )

        self.points[r] = [cur_x, cur_y]

        if len(self.points) > 1:
            self.draw_polygon()

    def draw_polygon(self):
        self.canvas.delete("poly")
        self.canvas.create_polygon(
            sum(self.points.values(), []),
            tags="poly",
            fill='',
            outline='#00ff00',
            dash=(5,),
            width=2
        )

        # update region lookup table
        new_points = np.array(list(self.points.values()), dtype=np.uint)
        label = self.current_label.get()
        self.img_region_lut[
            self.current_img
        ][label][self.current_reg_idx] = new_points

    def grab_handle(self, event):
        # button 1 was pressed so make sure canvas has focus
        self.canvas.focus_set()

        self.selected_handle = None

        # have to translate our event position to our current panned location
        selection = self.canvas.find_overlapping(
            self.canvas.canvasx(event.x) - HANDLE_RADIUS,
            self.canvas.canvasy(event.y) - HANDLE_RADIUS,
            self.canvas.canvasx(event.x) + HANDLE_RADIUS,
            self.canvas.canvasy(event.y) + HANDLE_RADIUS
        )

        for item in selection:
            tags = self.canvas.gettags(item)

            if 'handle' not in tags:
                # this isn't a handle object, do nothing
                continue
            else:
                self.selected_handle = item
                break

    def move_handle(self, event):
        if self.selected_handle is not None:
            # update handle position with mouse position
            self.canvas.coords(
                self.selected_handle,
                self.canvas.canvasx(event.x - HANDLE_RADIUS),
                self.canvas.canvasy(event.y - HANDLE_RADIUS),
                self.canvas.canvasx(event.x + HANDLE_RADIUS),
                self.canvas.canvasy(event.y + HANDLE_RADIUS)
            )

    def release_handle(self, event):
        if self.selected_handle is not None:
            self.move_handle(event)
            self.points[self.selected_handle] = [
                self.canvas.canvasx(event.x),
                self.canvas.canvasy(event.y)
            ]
            self.draw_polygon()

    def new_region(self):
        label = self.current_label.get()
        if label not in self.img_region_lut[self.current_img]:
            self.img_region_lut[self.current_img][label] = []
            self.current_reg_idx = 0

        count = len(self.img_region_lut[self.current_img][label])
        self.img_region_lut[self.current_img][label].append([])
        self.region_list_box.insert(tk.END, str(count + 1))
        self.region_list_box.selection_clear(self.current_reg_idx)
        self.region_list_box.selection_set(count)
        self.current_reg_idx = self.region_list_box.curselection()[0]
        self.clear_drawn_regions()

    def delete_region(self):
        label = self.current_label.get()
        del self.img_region_lut[self.current_img][label][self.current_reg_idx]
        self.region_list_box.delete(self.current_reg_idx)
        self.current_reg_idx = None
        self.clear_drawn_regions()

    def on_pan_button_press(self, event):
        self.canvas.config(cursor='fleur')

        # starting position for panning
        self.pan_start_x = int(self.canvas.canvasx(event.x))
        self.pan_start_y = int(self.canvas.canvasy(event.y))

    def pan_image(self, event):
        self.canvas.scan_dragto(
            event.x - self.pan_start_x,
            event.y - self.pan_start_y,
            gain=1
        )

    # noinspection PyUnusedLocal
    def on_pan_button_release(self, event):
        self.canvas.config(cursor='tcross')

    def clear_drawn_regions(self):
        self.canvas.delete("poly")
        self.canvas.delete("handle")
        self.points = OrderedDict()

    def _new_label(self):
        self.region_label_set.add(self.new_label_var.get())
        self.label_option['values'] = sorted(self.region_label_set)

    def new_label(self):
        new_label_dialog = tk.Toplevel(self)
        new_label_dialog.config(bg=BACKGROUND_COLOR)
        new_label_dialog.wm_title("Create New Label")

        new_label_entry = ttk.Entry(
            new_label_dialog,
            textvariable=self.new_label_var
        )
        new_label_entry.pack(
            side="top",
            fill="both",
            expand=True,
            padx=PAD_MEDIUM,
            pady=PAD_MEDIUM
        )

        cancel_button = ttk.Button(
            new_label_dialog,
            text='Cancel',
            command=new_label_dialog.destroy
        )
        cancel_button.pack(
            side=tk.RIGHT,
            anchor=tk.N,
            padx=PAD_SMALL,
            pady=PAD_MEDIUM
        )
        confirm_button = ttk.Button(
            new_label_dialog,
            text='Create',
            command=self._new_label
        )
        confirm_button.pack(
            side=tk.RIGHT,
            anchor=tk.N,
            padx=PAD_SMALL,
            pady=PAD_MEDIUM
        )

    def load_regions_json(self, regions_file_path):
        # Each image set directory will have a 'regions.json' file. This regions
        # file has keys of the image file names in the image set, and the value
        # for each image is a list of segmented polygon regions.
        # First, we will read in this file and get the file names for our images
        regions_file = open(regions_file_path)
        self.base_dir = os.path.dirname(regions_file_path)

        regions_json = json.load(regions_file)
        regions_file.close()

        # output will be a dictionary regions, where the
        # polygon points dict is a numpy array.
        # The keys are the image names
        self.img_region_lut = {}
        self.region_label_set = set()

        # clear the list box and the relevant file_list keys
        self.file_list_box.delete(0, tk.END)
        self.region_list_box.delete(0, tk.END)

        for image_name, regions_dict in regions_json.items():
            self.file_list_box.insert(tk.END, image_name)

            self.img_region_lut[image_name] = {}

            for label, regions in regions_dict.items():
                self.region_label_set.add(label)

                for region in regions:
                    points = np.empty((0, 2), dtype='int')

                    for point in region:
                        points = np.append(points, [[point[0], point[1]]], axis=0)

                    if label not in self.img_region_lut[image_name]:
                        self.img_region_lut[image_name][label] = []

                    self.img_region_lut[image_name][label].append(points)

        self.label_option['values'] = sorted(self.region_label_set)

    def save_regions_json(self):
        save_file = filedialog.asksaveasfile(defaultextension=".json")
        if save_file is None:
            return

        def my_converter(o):
            if isinstance(o, np.ndarray):
                return o.tolist()

        json.dump(
            self.img_region_lut,
            save_file,
            indent=2,
            default=my_converter
        )

    # noinspection PyUnusedLocal
    def select_file(self, event):
        current_sel = self.file_list_box.curselection()
        self.current_img = self.file_list_box.get(current_sel[0])
        img_path = os.path.join(self.base_dir, self.current_img)
        cv_img = cv2.imread(img_path)

        image = PIL.Image.fromarray(
            cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB),
            'RGB'
        )
        self.tk_image = PIL.ImageTk.PhotoImage(image)
        height, width = image.size
        self.image_dims = (height, width)
        self.canvas.config(scrollregion=(0, 0, height, width))
        self.canvas.create_image(
            0,
            0,
            anchor=tk.NW,
            image=self.tk_image
        )

        self.select_label(event)

    # noinspection PyUnusedLocal
    def select_label(self, event):
        # clear the list box
        self.region_list_box.delete(0, tk.END)
        self.clear_drawn_regions()

        label = self.current_label.get()

        if label not in self.img_region_lut[self.current_img]:
            return

        for i, r in enumerate(self.img_region_lut[self.current_img][label]):
            self.region_list_box.insert(tk.END, i + 1)

    # noinspection PyUnusedLocal
    def select_region(self, event):
        r_idx = self.region_list_box.curselection()
        if len(r_idx) == 0:
            self.current_reg_idx = None
            return

        self.current_reg_idx = r_idx[0]
        label = self.current_label.get()
        region = self.img_region_lut[self.current_img][label][r_idx[0]]

        self.clear_drawn_regions()

        if len(region) == 0:
            return

        for point in region:
            e = tk.Event()
            e.x, e.y = point

            self.draw_point(e, override_focus=True)

        min_x, min_y, reg_w, reg_h = cv2.boundingRect(region)
        min_x = min_x + (reg_w / 2.0)
        min_y = min_y + (reg_h / 2.0)

        c_h = self.canvas.winfo_height() / 2
        c_w = self.canvas.winfo_width() / 2
        self.canvas.xview_moveto((min_x - c_w) / self.image_dims[1])
        self.canvas.yview_moveto((min_y - c_h) / self.image_dims[0])

    def choose_new_img_file(self):
        selected_file = filedialog.askopenfile('r')

        if selected_file is None:
            return

        image_name = os.path.basename(selected_file.name)
        self.file_list_box.insert(tk.END, image_name)
        self.img_region_lut[image_name] = {}

    def choose_files(self):
        self.clear_drawn_regions()

        selected_file = filedialog.askopenfile('r')

        if selected_file is None:
            return

        self.load_regions_json(selected_file.name)


root = themed_tk.ThemedTk()
root.set_theme('arc')
app = Application(root)
root.mainloop()
