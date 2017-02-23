import tkinter
from tkinter import filedialog
from PIL import ImageTk
import PIL.Image
import os
import re
from collections import OrderedDict
import numpy as np
import cv2

BACKGROUND_COLOR = '#ededed'
HANDLE_RADIUS = 4  # not really a radius, just half a side length

WINDOW_WIDTH = 580
WINDOW_HEIGHT = 600

PAD_SMALL = 2
PAD_MEDIUM = 4
PAD_LARGE = 8
PAD_EXTRA_LARGE = 14


class Application(tkinter.Frame):

    def __init__(self, master):

        tkinter.Frame.__init__(self, master=master)

        self.image_name = None
        self.image_dir = None

        self.master.minsize(width=WINDOW_WIDTH, height=WINDOW_HEIGHT)

        file_chooser_frame = tkinter.Frame(self.master, bg=BACKGROUND_COLOR)
        file_chooser_frame.pack(
            fill=tkinter.X,
            expand=False,
            anchor=tkinter.N,
            padx=PAD_MEDIUM,
            pady=PAD_MEDIUM
        )

        file_chooser_button = tkinter.Button(
            file_chooser_frame,
            text='Choose Image File...',
            command=self.choose_files
        )
        file_chooser_button.pack(side=tkinter.LEFT)

        clear_regions_button = tkinter.Button(
            file_chooser_frame,
            text='Clear Regions',
            command=self.clear_rectangles
        )
        clear_regions_button.pack(side=tkinter.RIGHT, anchor=tkinter.N)

        self.snip_string = tkinter.StringVar()
        snip_label = tkinter.Label(
            file_chooser_frame,
            text="Snip Label: ",
            bg=BACKGROUND_COLOR
        )
        snip_label_entry = tkinter.Entry(
            file_chooser_frame,
            textvariable=self.snip_string
        )
        snip_label_entry.pack(side=tkinter.RIGHT)
        snip_label.pack(side=tkinter.RIGHT)

        # the canvas frame's contents will use grid b/c of the double
        # scrollbar (they don't look right using pack), but the canvas itself
        # will be packed in its frame
        canvas_frame = tkinter.Frame(self.master, bg=BACKGROUND_COLOR)
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        canvas_frame.pack(
            fill=tkinter.BOTH,
            expand=True,
            anchor=tkinter.N,
            padx=PAD_MEDIUM,
            pady=PAD_MEDIUM
        )

        self.canvas = tkinter.Canvas(
            canvas_frame,
            cursor="tcross",
            takefocus=1
        )

        self.scrollbar_v = tkinter.Scrollbar(
            canvas_frame,
            orient=tkinter.VERTICAL
        )
        self.scrollbar_h = tkinter.Scrollbar(
            canvas_frame,
            orient=tkinter.HORIZONTAL
        )
        self.scrollbar_v.config(command=self.canvas.yview)
        self.scrollbar_h.config(command=self.canvas.xview)

        self.canvas.config(yscrollcommand=self.scrollbar_v.set)
        self.canvas.config(xscrollcommand=self.scrollbar_h.set)

        self.canvas.grid(
            row=0,
            column=0,
            sticky=tkinter.N + tkinter.S + tkinter.E + tkinter.W
        )
        self.scrollbar_v.grid(row=0, column=1, sticky=tkinter.N + tkinter.S)
        self.scrollbar_h.grid(row=1, column=0, sticky=tkinter.E + tkinter.W)

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
        if not isinstance(self.focus_get(), tkinter.Canvas):
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

        output_dir = "/".join(
            [
                self.image_dir,
                self.snip_string.get().strip()
            ]
        )

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

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

        match = re.search('(.+)\.(.+)$', self.image_name)
        output_filename = "".join(
            [
                match.groups()[0],
                '_',
                str(x1),
                ',',
                str(y1)
            ]
        )
        mask_filename = "_".join(
            [
                output_filename,
                'mask'
            ]
        )
        output_filename = ".".join([output_filename, match.groups()[1]])
        mask_filename = ".".join([mask_filename, match.groups()[1]])

        output_file_path = "/".join([output_dir, output_filename])
        mask_file_path = "/".join([output_dir, mask_filename])

        region.save(output_file_path)
        cv2.imwrite(mask_file_path, poly_mask)

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

    def choose_files(self):
        self.canvas.delete("poly")
        self.canvas.delete("handle")
        self.points = OrderedDict()

        selected_file = filedialog.askopenfile('r')

        if selected_file is None:
            return

        cv_img = cv2.imread(selected_file.name)

        self.image = PIL.Image.fromarray(
            cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB),
            'RGB'
        )
        height, width = self.image.size
        self.canvas.config(scrollregion=(0, 0, height, width))
        self.tk_image = ImageTk.PhotoImage(self.image)
        self.canvas.create_image(0, 0, anchor=tkinter.NW, image=self.tk_image)

        self.image_name = os.path.basename(selected_file.name)
        self.image_dir = os.path.dirname(selected_file.name)

root = tkinter.Tk()
app = Application(root)
root.mainloop()
