import KAWAUtils
import json
from tkinter import *
from tkinter import ttk

def runGUI(material_options, ROIOptions_old, fertile_planets):
    root = Tk()
    root.title("KAWA ROI Calculator Option Selector")

    mainframe = ttk.Frame(root, padding=(3, 3, 12, 12))
    mainframe.pack(fill=BOTH, expand=1)

    # show fertile  planet options
    fertile_planet_list = []
    for key in fertile_planets.keys():
        fertile_planet_list.append('{}|{:.1f}'.format(key, fertile_planets[key]))
    fertileframe = ttk.Frame(mainframe)
    ttk.Label(fertileframe, text='Fertile Planet: ').pack(side=LEFT)
    fertile_planet_selection = StringVar(value='{}|{:.1f}'.format(ROIOptions_old['fertile_planet']['ID'], ROIOptions_old['fertile_planet']['Fertility']))
    OptionMenu(fertileframe, fertile_planet_selection, *fertile_planet_list).pack(side=LEFT)
    fertileframe.pack()

    # list all the materials and their recipe/planet options
    scrollcanvas = Canvas(mainframe, width=300,height=300)
    scrollbar = ttk.Scrollbar(mainframe, orient=VERTICAL)
    scrollbar.config(command=scrollcanvas.yview)
    scrollcanvas.config(yscrollcommand=scrollbar.set)
    scrollframe = ttk.Frame(scrollcanvas)
    material_selection_vars = {}
    for key in sorted(material_options.keys()):
        if material_options[key]:
            cur_options = material_options[key]
        else:
            cur_options = ['']
        temp_frame = ttk.Frame(scrollframe)
        ttk.Label(temp_frame, text='{}: '.format(key)).pack(side=LEFT)
        material_selection_vars[key] = StringVar(value=ROIOptions_old['preferred_recipes'][key])
        temp = OptionMenu(temp_frame, material_selection_vars[key], *cur_options)
        if len(cur_options) > 1:
            temp.config(bg="GREEN")
        temp.pack(side=LEFT)
        temp_frame.pack()

    scrollbar.pack(fill=Y, side=RIGHT)
    scrollframe.pack(fill=BOTH, expand=1)
    scrollframe_id = scrollcanvas.create_window(0, 0, window=scrollframe, anchor=NW)
    scrollcanvas.pack(fill=BOTH, expand=1, side=LEFT)

    def _configure_scrollframe(event):
        # Update the scrollbars to match the size of the inner frame.
        size = (scrollframe.winfo_reqwidth(), scrollframe.winfo_reqheight())
        scrollcanvas.config(scrollregion="0 0 %s %s" % size)
        if scrollframe.winfo_reqwidth() != scrollcanvas.winfo_width():
            # Update the canvas's width to fit the inner frame.
            scrollcanvas.config(width=scrollframe.winfo_reqwidth())
    scrollframe.bind('<Configure>', _configure_scrollframe)

    def _configure_scrollcanvas(event):
        if scrollframe.winfo_reqwidth() != scrollcanvas.winfo_width():
            # Update the inner frame's width to fill the canvas.
            scrollcanvas.itemconfigure(scrollframe_id, width=scrollcanvas.winfo_width())
    scrollcanvas.bind('<Configure>', _configure_scrollcanvas)
    root.mainloop()

    # create an ROIOptions dictionary to pass all selected values to user
    fertile_planet_key,_ = fertile_planet_selection.get().split('|')
    ROIOptions = {'fertile_planet': {'ID': fertile_planet_key, 'Fertility': fertile_planets[fertile_planet_key]}, 'preferred_recipes': {}}
    for key in sorted(material_selection_vars.keys()):
        ROIOptions['preferred_recipes'][key] = material_selection_vars[key].get()
    
    return ROIOptions

if __name__ == '__main__':
    # read FIO data from the cache or retrieve the date from FIO and cache it.
    buildings, recipes, materials, planets, materials_byID = KAWAUtils.read_FIO_data()
    
    # generate list of options
    material_options = {}
    for material in materials.values():
        option_list = []
        if 'PlanetList' in material:
            option_list.extend(material['PlanetList'])
        if 'RecipeList' in material:
            option_list.extend(material['RecipeList'])
        material_options[material['Ticker']] = option_list

    fertile_planets = {}
    for key in planets.keys():
        if planets[key]['Fertility'] > -1:
            fertile_planets[key] = ((planets[key]['Fertility'] * 10 / 33) + 1) * 100
    
    # with open('material_options.json', 'wt') as file:
    #     json.dump(material_options, file, indent='  ')
    
    # Load the material/recipe selections used in calculations
    with open('ROICalculatorOptions.json', 'rt') as file:
        ROIOptions_old = json.load(file)

    # Present options to user and save result
    ROIOptions = runGUI(material_options, ROIOptions_old, fertile_planets)
    
    with open('ROICalculatorOptions.json', 'wt') as file:
        json.dump(ROIOptions, file, indent='  ')