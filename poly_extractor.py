import tkinter as tk
import ttkthemes as themed_tk
from tkinter import filedialog, ttk
import PIL.Image
import PIL.ImageTk
import os
import json
from operator import itemgetter
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

WINDOW_WIDTH = 580
WINDOW_HEIGHT = 600

PAD_SMALL = 2
PAD_MEDIUM = 4
PAD_LARGE = 8
PAD_EXTRA_LARGE = 14


class Application(tk.Frame):

    def __init__(self, master):

        tk.Frame.__init__(self, master=master)

        self.images = None
        self.img_region_lut = None
        self.region_labels = None
        self.base_dir = None

        self.master.minsize(width=WINDOW_WIDTH, height=WINDOW_HEIGHT)
        self.master.config(bg=BACKGROUND_COLOR)

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

        clear_regions_button = ttk.Button(
            file_chooser_button_frame,
            text='Clear Regions',
            command=self.clear_rectangles
        )
        clear_regions_button.pack(side=tk.RIGHT, anchor=tk.N)

        self.snip_string = tk.StringVar()
        snip_label = ttk.Label(
            file_chooser_button_frame,
            text="Snip Label: "
        )
        snip_label.config(background=BACKGROUND_COLOR)
        snip_label_entry = ttk.Entry(
            file_chooser_button_frame,
            textvariable=self.snip_string
        )
        snip_label_entry.pack(side=tk.RIGHT)
        snip_label.pack(side=tk.RIGHT)

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

        region_scroll_bar = ttk.Scrollbar(region_list_frame, orient='vertical')
        self.region_list_box = tk.Listbox(
            region_list_frame,
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
        self.master.bind("<Return>", self.extract_region)
        self.master.bind("<p>", self.draw_point)

        self.points = OrderedDict()
        self.selected_handle = None

        self.start_x = None
        self.start_y = None

        self.pan_start_x = None
        self.pan_start_y = None

        self.image = None
        self.tk_image = None

        self.pack()

    def draw_point(self, event):
        # don't do anything unless the canvas has focus
        if not isinstance(self.focus_get(), tk.Canvas):
            return

        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)

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
            self.draw_polygon(event)

    # noinspection PyUnusedLocal
    def draw_polygon(self, event):
        self.canvas.delete("poly")
        self.canvas.create_polygon(
            sum(self.points.values(), []),
            tags="poly",
            fill='',
            outline='#00ff00',
            dash=(5,),
            width=2
        )

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
            self.draw_polygon(event)

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

    def clear_rectangles(self):
        self.canvas.delete("rect")
        self.canvas.delete("poly")
        self.canvas.delete("handle")
        self.points = OrderedDict()

    # noinspection PyUnusedLocal
    def extract_region(self, event):
        if len(self.points) < 3:
            return

        contour = np.array(list(self.points.values()), dtype='int')
        b_rect = cv2.boundingRect(contour)

        poly_mask = np.zeros(self.image.size, dtype=np.uint8)
        cv2.drawContours(poly_mask, [contour], 0, 255, cv2.FILLED)

        x1 = b_rect[0]
        x2 = b_rect[0] + b_rect[2]
        y1 = b_rect[1]
        y2 = b_rect[1] + b_rect[3]

        region = self.image.crop((x1, y1, x2, y2))
        poly_mask = poly_mask[y1:y2, x1:x2]

        self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            outline='#ff1493',
            width=2,
            tag='rect'
        )

        self.canvas.delete("poly")
        self.canvas.delete("handle")
        self.points = OrderedDict()

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

        # clear the list box and the relevant file_list keys
        self.file_list_box.delete(0, tk.END)

        for image_name, sub_regions in regions_json.items():
            self.file_list_box.insert(tk.END, image_name)

            self.img_region_lut[image_name] = {
                'hsv_img': None,
                'img_path': os.path.join(self.base_dir, image_name),
                'regions': []
            }

            for region in sub_regions:
                points = np.empty((0, 2), dtype='int')

                for point in sorted(region['points'], key=itemgetter('order')):
                    points = np.append(points, [[point['x'], point['y']]], axis=0)

                self.img_region_lut[image_name]['regions'].append(
                    {
                        'label': region['anatomy'],
                        'points': points
                    }
                )

    # noinspection PyUnusedLocal
    def select_file(self, event):
        current_sel = self.file_list_box.curselection()
        current_f_sel = self.file_list_box.get(current_sel[0])
        selected_img_path = self.img_region_lut[current_f_sel]['img_path']
        cv_img = cv2.imread(selected_img_path)

        self.image = PIL.Image.fromarray(
            cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB),
            'RGB'
        )
        height, width = self.image.size
        self.canvas.config(scrollregion=(0, 0, height, width))
        self.tk_image = PIL.ImageTk.PhotoImage(self.image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        # clear the list box
        self.region_list_box.delete(0, tk.END)

        for region in self.img_region_lut[current_f_sel]['regions']:
            self.region_list_box.insert(tk.END, region['label'])

    # noinspection PyUnusedLocal
    def select_region(self, event):
        pass

    def choose_files(self):
        self.canvas.delete("poly")
        self.canvas.delete("handle")
        self.points = OrderedDict()

        selected_file = filedialog.askopenfile('r')

        if selected_file is None:
            return

        self.load_regions_json(selected_file.name)


root = themed_tk.ThemedTk()
root.set_theme('arc')
app = Application(root)
root.mainloop()
