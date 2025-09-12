import sys
import urllib
import urllib.request
import json
import pickle
import os
import math

DAY_TIME_MS = 24*60*60*1000
REPAIR_PERIOD_DAYS = 60
REPAIR_PERIOD_MS = REPAIR_PERIOD_DAYS*DAY_TIME_MS
ROI_PERIOD_DAYS = 30
ROI_PERIOD_MS = ROI_PERIOD_DAYS*DAY_TIME_MS

class PopulationCost:
    def __init__(self, pioneer = 0, settler = 0, technician = 0, engineer = 0, scientist = 0):
        self.Pioneer = pioneer
        self.Settler = settler
        self.Technician = technician
        self.Engineer = engineer
        self.Scientist = scientist
        self.Extras = {}
    
    def __add__(self, other):
        pioneer = self.Pioneer + other.Pioneer
        settler = self.Settler + other.Settler
        technician = self.Technician + other.Technician
        engineer = self.Engineer + other.Engineer
        scientist = self.Scientist + other.Scientist
        return PopulationCost(pioneer, settler, technician, engineer, scientist)
    
    __radd__ = __add__
    
    def __sub__(self, other):
        pioneer = self.Pioneer - other.Pioneer
        settler = self.Settler - other.Settler
        technician = self.Technician - other.Technician
        engineer = self.Engineer - other.Engineer
        scientist = self.Scientist - other.Scientist
        return PopulationCost(pioneer, settler, technician, engineer, scientist)
    
    def __rsub__(self, other):
        pioneer = other.Pioneer - self.Pioneer
        settler = other.Settler - self.Settler
        technician = other.Technician - self.Technician
        engineer = other.Engineer - self.Engineer
        scientist = other.Scientist - self.Scientist
        return PopulationCost(pioneer, settler, technician, engineer, scientist)
    
    def __mul__(self, scaler):
        pioneer = self.Pioneer * scaler
        settler = self.Settler * scaler
        technician = self.Technician * scaler
        engineer = self.Engineer * scaler
        scientist = self.Scientist * scaler
        return PopulationCost(pioneer, settler, technician, engineer, scientist)
    
    __rmul__ = __mul__
    
    def __truediv__(self, scaler):
        pioneer = self.Pioneer / scaler
        settler = self.Settler / scaler
        technician = self.Technician / scaler
        engineer = self.Engineer / scaler
        scientist = self.Scientist / scaler
        return PopulationCost(pioneer, settler, technician, engineer, scientist)
    
    def __rtruediv__(self, scaler):
        pioneer = scaler / self.Pioneer
        settler = scaler / self.Settler
        technician = scaler / self.Technician
        engineer = scaler / self.Engineer
        scientist = scaler / self.Scientist
        return PopulationCost(pioneer, settler, technician, engineer, scientist)
    
    def __str__(self):
        return '({},{},{},{},{})'.format(self.Pioneer, self.Settler, self.Technician, self.Engineer, self.Scientist)

def query_FNAR_REST_list(url, key_field):
    # documentation: https://doc.fnar.net/
    out_dictionary = {}
    with urllib.request.urlopen(url) as query_response:
        query_list = json.loads(query_response.read())
        for item in query_list:
            if item[key_field] in out_dictionary:
                print('Found duplicate {} from {}: {}'.format(key_field, url, item[key_field]))
            out_dictionary[item[key_field]] = item
    return out_dictionary

def get_planet_build_requirements(planet):
    planet_specific_materials=[]
    for requirement in planet['BuildRequirements']:
        if requirement['MaterialTicker'] in ['LSE', 'TRU', 'PSL', 'LDE', 'LTA']:
            pass
        else:
            planet_specific_materials.append(requirement['MaterialTicker'])
    return planet_specific_materials

def get_recipe_output_from_material_type(material_type, factor):
    # https://pct.fnar.net/planet/
    if material_type == 'MINERAL':
        recipe_key = 'EXT:=>'
        output = 100*0.7/2*factor
    elif material_type == 'GASEOUS':
        recipe_key = 'COL:=>'
        output = 100*0.6/4*factor
    elif material_type == 'LIQUID':
        recipe_key = 'RIG:=>'
        output = 100*0.7/5*factor
    else:
        print('ERROR: unknown resource type: {}'.format(material_type))
    
    return recipe_key, output

def calculate_habitation_pair_needs(pop1, pop2, hab1, hab2, hab_comb):
    if pop2 > 0:
        if pop1 > pop2:
            hab_comb_count = math.ceil(pop2/75)
            leftover_pop1 = hab_comb_count*75 - pop1
            hab1_count = math.ceil(leftover_pop1/100)
            if hab1_count > 0:
                # hab_comb/hab1
                return [{'Ticker': hab1, 'Count': hab1_count},{'Ticker': hab_comb, 'Count': hab_comb_count}]
            else:
                # hab_comb
                return [{'Ticker': hab_comb, 'Count': hab_comb_count}]
        else:
            hab_comb_count = math.ceil(pop1/75)
            leftover_pop2 = hab_comb_count*75 - pop2
            hab2_count = math.ceil(leftover_pop2/100)
            if hab2_count > 0:
                # hab_comb/hab2
                return [{'Ticker': hab2, 'Count': hab2_count},{'Ticker': hab_comb, 'Count': hab_comb_count}]
            else:
                # hab_comb
                return [{'Ticker': hab_comb, 'Count': hab_comb_count}]
    else:
        # hab1
        hab1_count = math.ceil(pop1/100)
        return [{'Ticker': hab1, 'Count': hab1_count}]

def calculate_habitation_needs(pioneers, settlers, technicians, engineers, scientists):
    if pioneers > 0:
        return calculate_habitation_pair_needs(pioneers, settlers, 'HB1', 'HB2', 'HBB')
    elif settlers > 0:
        return calculate_habitation_pair_needs(settlers, technicians, 'HB2', 'HB3', 'HBC')
    elif technicians > 0:
        return calculate_habitation_pair_needs(technicians, engineers, 'HB3', 'HB4', 'HBM')
    elif engineers > 0:
        return calculate_habitation_pair_needs(engineers, scientists, 'HB4', 'HB5', 'HBL')
    elif scientists > 0:
        return calculate_habitation_pair_needs(scientists, 0, 'HB5', 'ERROR', 'ERROR')
    else:
        raise Exception('Error in calculate_habitation_needs.  No population given.')

def calculate_single_building_base_setup(building_ticker, buildings):
    # buildings to ignore
    if building_ticker in ['PAR', 'SDP', 'COG', 'CRC', 'HOS', 'UNI', 'LIB', 'PWH', 'LM', 'EMC', 'WCE', 'ART', '4DA', 'ADM', 'PSY', 'SST', 'INF', 'ACA', 'PBH', 'VRT', 'CM', 'STO', 'HB1', 'HB2', 'HB3', 'HB4', 'HB5', 'HBB', 'HBC', 'HBM', 'HBL']:
        return [], 0
    # initialize population and number of buildings
    building_count = 1
    pioneers = buildings[building_ticker]['Pioneers']
    settlers = buildings[building_ticker]['Settlers']
    technicians = buildings[building_ticker]['Technicians']
    engineers = buildings[building_ticker]['Engineers']
    scientists = buildings[building_ticker]['Scientists']

    # if pioneers+settlers+technicians+engineers+scientists == 0:
    #     print('here')

    while(True):
        # calculation habitation needs for current number of buildings
        building_list = calculate_habitation_needs(pioneers*building_count, settlers*building_count, technicians*building_count, engineers*building_count, scientists*building_count)
        building_list.append({'Ticker': building_ticker, 'Count': building_count})

        # calculate area needed for current set of buildings
        area = 0
        for cur_building in building_list:
            area = area + buildings[cur_building['Ticker']]['AreaCost']*cur_building['Count']
        
        # Complete once area exceeds 500
        if area > 500:
            break

        # Area has not exceeded 500.  Add another building and try again
        building_count = building_count + 1

    # Area exceeded 500 with the current building count.  Decrease the building count by 1 and return the set of bulidings
    building_count = building_count - 1
    building_list = calculate_habitation_needs(pioneers*building_count, settlers*building_count, technicians*building_count, engineers*building_count, scientists*building_count)
    building_list.append({'Ticker': building_ticker, 'Count': building_count})

    # Add area and material costs for all the buildings to this structure
    for building in building_list:
        building['BuildingCosts'] = buildings[building['Ticker']]['BuildingCosts']
        building['AreaCost'] = buildings[building['Ticker']]['AreaCost']

    return building_list, building_count

def calculate_desired_profit(cur_material, output_count, input_costs, repair_costs, recipe_time, planet_mats, base_cost_list, input_cost_list, repair_cost_list, desired_profit_list, base_setup, use_cur_material_costs = True):
    # Add desired profit: ROI in this case
    recipe_time_fraction = recipe_time/ROI_PERIOD_MS # fraction of ROI needed for each recipe run
    base_output_per_run = output_count*base_setup['BuildingCount']
    desired_profit = PopulationCost()
    for building in base_setup['BaseList']:
        for building_mat in building['BuildingCosts']:
            mat_ticker = building_mat['CommodityTicker']
            mat_build_quantity = building_mat['Amount']*building['Count']
            if use_cur_material_costs and mat_ticker == cur_material:
                input_cost_cur = input_costs
                repair_cost_cur = repair_costs
                desired_profit_cur = desired_profit
            else:
                input_cost_cur = input_cost_list[mat_ticker]
                repair_cost_cur = repair_cost_list[mat_ticker]
                desired_profit_cur = desired_profit_list[mat_ticker]
            desired_profit += recipe_time_fraction/base_output_per_run*mat_build_quantity*(base_cost_list[mat_ticker] + input_cost_cur + repair_cost_cur + desired_profit_cur)
        # add something for MCG and any other planet based materials
        for mat_ticker in planet_mats:
            if mat_ticker == 'MCG':
                mat_build_quantity = 4*building['AreaCost']
            elif mat_ticker == 'AEF':
                mat_build_quantity = math.ceil(building['AreaCost']/3)
            elif mat_ticker == 'SEA':
                mat_build_quantity = 1*building['AreaCost']
            elif mat_ticker == 'INS':
                mat_build_quantity = 10*building['AreaCost']
            elif mat_ticker in ['HSE', 'TSH', 'BL', 'MGC']:
                mat_build_quantity = 1
            else:
                print('ERROR: planet material not recognized: {}'.format(mat_ticker))
            if use_cur_material_costs and mat_ticker == cur_material:
                input_cost_cur = input_costs
                repair_cost_cur = repair_costs
                desired_profit_cur = desired_profit
            else:
                input_cost_cur = input_cost_list[mat_ticker]
                repair_cost_cur = repair_cost_list[mat_ticker]
                desired_profit_cur = desired_profit_list[mat_ticker]
            desired_profit = desired_profit + recipe_time_fraction/base_output_per_run*mat_build_quantity*(base_cost_list[mat_ticker] + input_cost_cur + repair_cost_cur + desired_profit_cur)
    
    return desired_profit

def calculate_population_cost(output_count, building, recipe_time):
    # Calculate population costs
    time_quant_factor = recipe_time/output_count
    population_cost = PopulationCost(building['Pioneers']*time_quant_factor,building['Settlers']*time_quant_factor,building['Technicians']*time_quant_factor,building['Engineers']*time_quant_factor,building['Scientists']*time_quant_factor)
    return population_cost

def calculate_input_cost(cur_material, output_count, inputs, base_cost_list, input_cost_list, repair_cost_list, desired_profit_list, use_cur_material_costs = True):
    # Calculate input costs
    input_costs = PopulationCost()
    for input_mat in inputs:
        mat_ticker = input_mat['Ticker']
        if use_cur_material_costs and mat_ticker == cur_material:
            input_cost_cur = input_costs
        else:
            input_cost_cur = input_cost_list[mat_ticker]
        input_costs = input_costs + input_mat['Amount']/output_count*(base_cost_list[mat_ticker] + input_cost_cur + repair_cost_list[mat_ticker] + desired_profit_list[mat_ticker])
    
    return input_costs

def calculate_repair_cost(cur_material, output_count, building_costs, input_costs, recipe_time, building_area_cost, planet_mats, base_cost_list, input_cost_list, repair_cost_list, desired_profit_list, use_cur_material_costs = True):
    # Add repair costs
    repair_material_fraction = REPAIR_PERIOD_DAYS/180 # fraction of repair materials needed due to repair time
    recipe_time_fraction = recipe_time/REPAIR_PERIOD_MS # fraction of repair materials needed for each recipe run
    repair_costs = PopulationCost()
    for building_mat in building_costs:
        mat_ticker = building_mat['CommodityTicker']
        mat_build_quantity = building_mat['Amount']
        mat_repair_quantity = math.ceil(repair_material_fraction*mat_build_quantity)
        if use_cur_material_costs and mat_ticker == cur_material:
            input_cost_cur = input_costs
            repair_cost_cur = repair_costs
        else:
            input_cost_cur = input_cost_list[mat_ticker]
            repair_cost_cur = repair_cost_list[mat_ticker]
        repair_costs = repair_costs + recipe_time_fraction/output_count*mat_repair_quantity*(base_cost_list[mat_ticker] + input_cost_cur + repair_cost_cur + desired_profit_list[mat_ticker])
    # add something for MCG and any other planet based materials
    for mat_ticker in planet_mats:
        if mat_ticker == 'MCG':
            mat_build_quantity = 4*building_area_cost
            mat_repair_quantity = math.ceil(repair_material_fraction*mat_build_quantity)
        elif mat_ticker == 'AEF':
            mat_build_quantity = math.ceil(building_area_cost/3)
            mat_repair_quantity = math.ceil(repair_material_fraction*mat_build_quantity)
        elif mat_ticker == 'SEA':
            mat_build_quantity = 1*building_area_cost
            mat_repair_quantity = math.ceil(repair_material_fraction*mat_build_quantity)
        elif mat_ticker == 'INS':
            mat_build_quantity = 10*building_area_cost
            mat_repair_quantity = math.ceil(repair_material_fraction*mat_build_quantity)
        elif mat_ticker in ['HSE', 'TSH', 'BL', 'MGC']:
            mat_build_quantity = 1
            mat_repair_quantity = 1
        else:
            print('ERROR: planet material not recognized: {}'.format(mat_ticker))
        if use_cur_material_costs and mat_ticker == cur_material:
            input_cost_cur = input_costs
            repair_cost_cur = repair_costs
        else:
            input_cost_cur = input_cost_list[mat_ticker]
            repair_cost_cur = repair_cost_list[mat_ticker]
        repair_costs = repair_costs + recipe_time_fraction/output_count*mat_repair_quantity*(base_cost_list[mat_ticker] + input_cost_cur + repair_cost_cur + desired_profit_list[mat_ticker])
    
    return repair_costs

def calculate_total_cost(cur_material, output_count, inputs, building_costs, recipe_time, building_area_cost, planet_mats, base_cost_list, input_cost_list, repair_cost_list, desired_profit_list, base_cost, base_setup, use_cur_material_costs = True):
    input_costs = calculate_input_cost(cur_material, output_count, inputs, base_cost_list, input_cost_list, repair_cost_list, desired_profit_list, use_cur_material_costs)
    
    repair_costs = calculate_repair_cost(cur_material, output_count, building_costs, input_costs, recipe_time, building_area_cost, planet_mats, base_cost_list, input_cost_list, repair_cost_list, desired_profit_list, use_cur_material_costs)

    desired_profit = calculate_desired_profit(cur_material, output_count, input_costs, repair_costs, recipe_time, planet_mats, base_cost_list, input_cost_list, repair_cost_list, desired_profit_list, base_setup, use_cur_material_costs)

    # calculate total costs
    total_costs = PopulationCost()
    total_costs = base_cost + input_costs + repair_costs + desired_profit
    
    return input_costs, repair_costs, desired_profit, total_costs

if __name__ == '__main__':
    # test = PopulationCost(1,0,0,0,0)
    # print(test*1)
    # sys.exit()
    # args = sys.argv[1:]
    # username = input('username:')
    # password = getpass.getpass('password:')
    cache_file = "cache.pickle"
    if os.path.isfile(cache_file):
        with open(cache_file, 'rb') as file:
            print('reading pickle file')
            buildings, recipes, materials, planets = pickle.load(file)
    else:
        buildings = query_FNAR_REST_list('https://rest.fnar.net/building/allbuildings', 'Ticker')
        recipes = query_FNAR_REST_list('https://rest.fnar.net/recipes/allrecipes', 'StandardRecipeName')
        materials = query_FNAR_REST_list('https://rest.fnar.net/material/allmaterials', 'Ticker')
        planets = query_FNAR_REST_list('https://rest.fnar.net/planet/allplanets/full', 'PlanetNaturalId')
        with open(cache_file, 'wb') as file:
            print('writing pickle file')
            pickle.dump([buildings, recipes, materials, planets], file)

    materials_byID = {}
    for material in materials.values():
        if material['MaterialId'] in materials_byID:
            print('Found duplicate material ID: %s'.format(material['MaterialId']))
        materials_byID[material['MaterialId']] = material['Ticker']

    for recipe in recipes.values():
        for item in recipe['Outputs']:
            if item['Ticker'] in materials:
                if 'RecipeList' in materials[item['Ticker']]:
                    materials[item['Ticker']]['RecipeList'].append(recipe['StandardRecipeName'])
                else:
                    materials[item['Ticker']]['RecipeList'] = [recipe['StandardRecipeName']]
            else:
                print('recipe: {}, output: {}, not found in materials.'.format(recipe, item))
    
    for planet in planets.values():
        for item in planet['Resources']:
            if item['MaterialId'] in materials_byID:
                if 'PlanetList' in materials[materials_byID[item['MaterialId']]]:
                    materials[materials_byID[item['MaterialId']]]['PlanetList'].append(planet['PlanetNaturalId'])
                else:
                    materials[materials_byID[item['MaterialId']]]['PlanetList'] = [planet['PlanetNaturalId']]
            else:
                print('planet: {}, resource: {}, not found in materials.'.format(planet, item))

    base_setups = {}
    for building in buildings.keys():
        base_list, building_count = calculate_single_building_base_setup(building, buildings)
        base_setups[building] = {'BaseList': base_list, 'BuildingCount': building_count}
    
    # printAllMaterialOptions = True
    # with open('material_options.txt', 'wt') as file:
    #     for material in materials.values():
    #         recipe_list = ''
    #         planet_list = ''
    #         optionsGT1 = False
    #         if 'RecipeList' in material:
    #             recipe_list = ','.join(material['RecipeList'])
    #             if len(material['RecipeList']) > 1 or ('PlanetList' in material):
    #                 optionsGT1 = True
    #         if 'PlanetList' in material:
    #             planet_list = ','.join(material['PlanetList'])
    #             if len(material['PlanetList']) > 1:
    #                 optionsGT1 = True
    #         if printAllMaterialOptions or optionsGT1:
    #             print('{}: {}| {}.'.format(material['Ticker'], recipe_list, planet_list),file=file)
    
    with open('material_selections.json', 'rt') as file:
        recipe_selections = json.load(file)

    # initialize costs
    material_costs = {}
    input_costs = {}
    repair_costs = {}
    desired_profit = {}
    total_costs = {}
    input_costs_new = {}
    repair_costs_new = {}
    total_costs_new = {}
    for material in materials.keys():
        planet_specific_materials = ['MCG']
        if not recipe_selections[material]:
            continue
        elif '=>' in recipe_selections[material]:
            recipe = recipes[recipe_selections[material]]
            output = 0
            for cur in recipe['Outputs']:
                if cur['Ticker'] == material:
                    output = cur['Amount']
        else:
            planet = planets[recipe_selections[material]]
            planet_specific_materials = get_planet_build_requirements(planet)
            materialinfo = {}
            for resource in planet['Resources']:
                if materials_byID[resource['MaterialId']] == material:
                    materialinfo = resource
                    materialinfo['Ticker'] = material
                    break
            if 'ResourceType' not in materialinfo:
                print('ERROR: {} not found.'.format(material))
            
            recipe_key, output = get_recipe_output_from_material_type(materialinfo['ResourceType'], materialinfo['Factor'])
            recipe = recipes[recipe_key]

        # print('{},{},{}'.format(material, recipe['StandardRecipeName'], output))
        material_costs[material] = calculate_population_cost(output, buildings[recipe['BuildingTicker']], recipe['TimeMs'])
        material_costs[material].Extras['recipe'] = recipe
        material_costs[material].Extras['output'] = output
        material_costs[material].Extras['planet_mats'] = planet_specific_materials
        input_costs[material] = PopulationCost()
        repair_costs[material] = PopulationCost()
        desired_profit[material] = PopulationCost()
        total_costs[material] = PopulationCost()

    # iterate over materials to find final cost
    for n in range(100):
        max_diff_elem = {'diff':-1, 'mat':''}
        for material in material_costs.keys():
            
            input_costs_temp, repair_costs_temp, desired_profit_temp, total_costs_temp = calculate_total_cost(material, material_costs[material].Extras['output'], material_costs[material].Extras['recipe']['Inputs'], buildings[material_costs[material].Extras['recipe']['BuildingTicker']]['BuildingCosts'], material_costs[material].Extras['recipe']['TimeMs'], buildings[material_costs[material].Extras['recipe']['BuildingTicker']]['AreaCost'], material_costs[material].Extras['planet_mats'], material_costs, input_costs, repair_costs, desired_profit, material_costs[material], base_setups[material_costs[material].Extras['recipe']['BuildingTicker']])
            population_diff = total_costs_temp - total_costs[material]
            diff_sum = population_diff.Pioneer+population_diff.Settler+population_diff.Technician+population_diff.Engineer+population_diff.Scientist
            if diff_sum > max_diff_elem['diff']:
                max_diff_elem['diff'] = diff_sum
                max_diff_elem['mat'] = material
            input_costs[material] = input_costs_temp
            repair_costs[material] = repair_costs_temp
            desired_profit[material] = desired_profit_temp
            total_costs[material] = total_costs_temp
            # if input_costs_temp != input_costs[material]:
            #     print("input_costs_temp ({}) does not equal input_costs[{}] ({})".format(input_costs_temp, material, input_costs[material]))
            # if repair_costs_temp != repair_costs[material]:
            #     print("repair_costs_temp ({}) does not equal repair_costs[{}] ({})".format(repair_costs_temp, material, repair_costs[material]))
            # if total_costs_temp != total_costs[material]:
            #     print("total_costs_temp ({}) does not equal total_costs[{}] ({})".format(total_costs_temp, material, total_costs[material]))
        print('Largest difference: {} {} ({}, {}, {}, {}, {})'.format(max_diff_elem['mat'], max_diff_elem['diff'], total_costs[max_diff_elem['mat']].Pioneer, total_costs[max_diff_elem['mat']].Settler, total_costs[max_diff_elem['mat']].Technician, total_costs[max_diff_elem['mat']].Engineer, total_costs[max_diff_elem['mat']].Scientist))
        if max_diff_elem['diff'] < 0.001:
            print('Iterations completed at n={}'.format(n))
            break

    # Cost all recipes based on the selected material recipes
    

    # calculate costs for workers
    PIO = PopulationCost()
    SET = PopulationCost()
    TEC = PopulationCost()
    ENG = PopulationCost()
    SCI = PopulationCost()
    # consumable costs per day per 100 units of population
    for item in [{'mat':'COF','amount':0.5},{'mat':'DW','amount':4},{'mat':'RAT','amount':4},{'mat':'OVE','amount':0.5},{'mat':'PWO','amount':0.2}]:
        PIO = PIO + total_costs[item['mat']]*item['amount']
    for item in [{'mat':'DW','amount':5},{'mat':'RAT','amount':6},{'mat':'KOM','amount':1},{'mat':'EXO','amount':0.5},{'mat':'REP','amount':0.2},{'mat':'PT','amount':0.5}]:
        SET = SET + total_costs[item['mat']]*item['amount']
    for item in [{'mat':'DW','amount':7.5},{'mat':'RAT','amount':7},{'mat':'ALE','amount':1},{'mat':'MED','amount':0.5},{'mat':'SC','amount':0.1},{'mat':'HMS','amount':0.5},{'mat':'SCN','amount':0.1}]:
        TEC = TEC + total_costs[item['mat']]*item['amount']
    for item in [{'mat':'DW','amount':10},{'mat':'MED','amount':0.5},{'mat':'GIN','amount':1},{'mat':'FIM','amount':7},{'mat':'VG','amount':0.2},{'mat':'HSS','amount':0.2},{'mat':'PDA','amount':0.1}]:
        ENG = ENG + total_costs[item['mat']]*item['amount']
    for item in [{'mat':'DW','amount':10},{'mat':'MED','amount':0.5},{'mat':'WIN','amount':1},{'mat':'MEA','amount':7},{'mat':'NST','amount':0.1},{'mat':'LC','amount':0.2},{'mat':'WS','amount':0.1}]:
        SCI = SCI + total_costs[item['mat']]*item['amount']
    
    # scale to 1 unit of population per ms.
    Apio = PIO.Pioneer/100/DAY_TIME_MS
    Bpio = PIO.Settler/100/DAY_TIME_MS
    Cpio = PIO.Technician/100/DAY_TIME_MS
    Dpio = PIO.Engineer/100/DAY_TIME_MS
    Epio = PIO.Scientist/100/DAY_TIME_MS
    
    Aset = SET.Pioneer/100/DAY_TIME_MS
    Bset = SET.Settler/100/DAY_TIME_MS
    Cset = SET.Technician/100/DAY_TIME_MS
    Dset = SET.Engineer/100/DAY_TIME_MS
    Eset = SET.Scientist/100/DAY_TIME_MS
    
    Atec = TEC.Pioneer/100/DAY_TIME_MS
    Btec = TEC.Settler/100/DAY_TIME_MS
    Ctec = TEC.Technician/100/DAY_TIME_MS
    Dtec = TEC.Engineer/100/DAY_TIME_MS
    Etec = TEC.Scientist/100/DAY_TIME_MS
    
    Aeng = ENG.Pioneer/100/DAY_TIME_MS
    Beng = ENG.Settler/100/DAY_TIME_MS
    Ceng = ENG.Technician/100/DAY_TIME_MS
    Deng = ENG.Engineer/100/DAY_TIME_MS
    Eeng = ENG.Scientist/100/DAY_TIME_MS
    
    Asci = SCI.Pioneer/100/DAY_TIME_MS
    Bsci = SCI.Settler/100/DAY_TIME_MS
    Csci = SCI.Technician/100/DAY_TIME_MS
    Dsci = SCI.Engineer/100/DAY_TIME_MS
    Esci = SCI.Scientist/100/DAY_TIME_MS

    PIOc = SETc = TECc = ENGc = SCIc = 500
    PIOc = 2.0e-7
    previous = [PIOc, SETc, TECc, ENGc, SCIc]
    for n in range(100):
        # PIOc = (            SETc*Bpio + TECc*Cpio + ENGc*Dpio + SCIc*Epio)/(1 - Apio)
        SETc = (PIOc*Aset +             TECc*Cset + ENGc*Dset + SCIc*Eset)/(1 - Bset)
        TECc = (PIOc*Atec + SETc*Btec +             ENGc*Dtec + SCIc*Etec)/(1 - Ctec)
        ENGc = (PIOc*Aeng + SETc*Beng + TECc*Ceng +             SCIc*Eeng)/(1 - Deng)
        SCIc = (PIOc*Asci + SETc*Bsci + TECc*Csci + ENGc*Dsci            )/(1 - Esci)
        print('PIO: {}, SET: {}, TEC: {}, ENG: {}, SCI: {}'.format(PIOc, SETc, TECc, ENGc, SCIc))
        current = [PIOc, SETc, TECc, ENGc, SCIc]
        test = map(lambda a,b: abs(a-b), current, previous)
        if max(map(lambda a,b: abs(a-b), current, previous)) < 1e-16:
            print('iteration finished at n = {}'.format(n))
            break
        previous = current


    total_costs_ts = {}
    repair_costs_ts = {}
    input_costs_ts = {}
    desired_profit_ts = {}
    material_costs_ts = {}
    with open('material_costs.csv', 'w') as file:
        file.write('{}, {}, {}, {}, {}, {}\n'.format('material', 'total cost', 'repair cost', 'input cost', 'desired profit', 'base unit cost'))
        for material in total_costs.keys():
            total_costs_ts[material] = total_costs[material].Pioneer*PIOc + total_costs[material].Settler*SETc + total_costs[material].Technician*TECc + total_costs[material].Engineer*ENGc + total_costs[material].Scientist*SCIc
            repair_costs_ts[material] = repair_costs[material].Pioneer*PIOc + repair_costs[material].Settler*SETc + repair_costs[material].Technician*TECc + repair_costs[material].Engineer*ENGc + repair_costs[material].Scientist*SCIc
            input_costs_ts[material] = input_costs[material].Pioneer*PIOc + input_costs[material].Settler*SETc + input_costs[material].Technician*TECc + input_costs[material].Engineer*ENGc + input_costs[material].Scientist*SCIc
            desired_profit_ts[material] = desired_profit[material].Pioneer*PIOc + desired_profit[material].Settler*SETc + desired_profit[material].Technician*TECc + desired_profit[material].Engineer*ENGc + desired_profit[material].Scientist*SCIc
            material_costs_ts[material] = material_costs[material].Pioneer*PIOc + material_costs[material].Settler*SETc + material_costs[material].Technician*TECc + material_costs[material].Engineer*ENGc + material_costs[material].Scientist*SCIc
            file.write('{}, {}, {}, {}, {}, {}\n'.format(material, total_costs_ts[material], repair_costs_ts[material], input_costs_ts[material], desired_profit_ts[material], material_costs_ts[material]))
    
    with open('recipe_costs.csv', 'w') as file:
        file.write('{}, {}, {}, {}, {}, {}\n'.format('recipe', 'total cost', 'repair cost', 'input cost', 'desired profit', 'base recipe cost'))
        planet_mats = ['MCG']
        for recipe in recipes.values():
            if not recipe['Outputs']:
                continue
            recipe_time = recipe['TimeMs']
            building = buildings[recipe['BuildingTicker']]
            recipe_cost = calculate_population_cost(1, building, recipe_time)
            input_costs_temp, repair_costs_temp, desired_profit_temp, total_costs_temp = calculate_total_cost('', 1, recipe['Inputs'], building['BuildingCosts'], recipe['TimeMs'], building['AreaCost'], planet_mats, material_costs, input_costs, repair_costs, desired_profit, recipe_cost, base_setups[recipe['BuildingTicker']], False)

            total_costs_temp_ts = total_costs_temp.Pioneer*PIOc + total_costs_temp.Settler*SETc + total_costs_temp.Technician*TECc + total_costs_temp.Engineer*ENGc + total_costs_temp.Scientist*SCIc
            repair_costs_temp_ts = repair_costs_temp.Pioneer*PIOc + repair_costs_temp.Settler*SETc + repair_costs_temp.Technician*TECc + repair_costs_temp.Engineer*ENGc + repair_costs_temp.Scientist*SCIc
            input_costs_temp_ts = input_costs_temp.Pioneer*PIOc + input_costs_temp.Settler*SETc + input_costs_temp.Technician*TECc + input_costs_temp.Engineer*ENGc + input_costs_temp.Scientist*SCIc
            desired_profit_ts = desired_profit_temp.Pioneer*PIOc + desired_profit_temp.Settler*SETc + desired_profit_temp.Technician*TECc + desired_profit_temp.Engineer*ENGc + desired_profit_temp.Scientist*SCIc
            recipe_cost_ts = recipe_cost.Pioneer*PIOc + recipe_cost.Settler*SETc + recipe_cost.Technician*TECc + recipe_cost.Engineer*ENGc + recipe_cost.Scientist*SCIc
            file.write('{}, {}, {}, {}, {}, {}\n'.format(recipe['StandardRecipeName'], total_costs_temp_ts, repair_costs_temp_ts, input_costs_temp_ts, desired_profit_ts, recipe_cost_ts))
    
    with open('natural_resource_costs.csv','w') as file:
        file.write('{}, {}, {}, {}, {}, {}, {}\n'.format('planet', 'material', 'total cost', 'repair cost', 'input cost', 'desired profit', 'base recipe cost'))
        natural_resource_building_cost = {}
        for building_ticker in ['COL', 'EXT', 'RIG']:
            recipe_key = '{}:=>'.format(building_ticker)
            recipe_time = recipes[recipe_key]['TimeMs']
            building = buildings[building_ticker]
            natural_resource_building_cost[recipe_key] = calculate_population_cost(1, building, recipe_time)
        
        for planet in planets.values():
            planet_specific_materials = get_planet_build_requirements(planet)
            for item in planet['Resources']:
                material_ticker = materials_byID[item['MaterialId']]
                recipe_key, output = get_recipe_output_from_material_type(item['ResourceType'], item['Factor'])
                recipe = recipes[recipe_key]
                building = buildings[recipe['BuildingTicker']]
                base_cost = {}
                base_cost = natural_resource_building_cost[recipe_key]/output
                
                input_costs_temp, repair_costs_temp, desired_profit_temp, total_costs_temp = calculate_total_cost('', output, recipe['Inputs'], building['BuildingCosts'], recipe['TimeMs'], building['AreaCost'], planet_specific_materials, material_costs, input_costs, repair_costs, desired_profit, base_cost, base_setups[recipe['BuildingTicker']], False)

                total_costs_temp_ts = total_costs_temp.Pioneer*PIOc + total_costs_temp.Settler*SETc + total_costs_temp.Technician*TECc + total_costs_temp.Engineer*ENGc + total_costs_temp.Scientist*SCIc
                repair_costs_temp_ts = repair_costs_temp.Pioneer*PIOc + repair_costs_temp.Settler*SETc + repair_costs_temp.Technician*TECc + repair_costs_temp.Engineer*ENGc + repair_costs_temp.Scientist*SCIc
                input_costs_temp_ts = input_costs_temp.Pioneer*PIOc + input_costs_temp.Settler*SETc + input_costs_temp.Technician*TECc + input_costs_temp.Engineer*ENGc + input_costs_temp.Scientist*SCIc
                desired_profit_temp_ts = desired_profit_temp.Pioneer*PIOc + desired_profit_temp.Settler*SETc + desired_profit_temp.Technician*TECc + desired_profit_temp.Engineer*ENGc + desired_profit_temp.Scientist*SCIc
                base_cost_ts = base_cost.Pioneer*PIOc + base_cost.Settler*SETc + base_cost.Technician*TECc + base_cost.Engineer*ENGc + base_cost.Scientist*SCIc
                file.write('{}, {}, {}, {}, {}, {}, {}\n'.format(planet['PlanetNaturalId'], material_ticker, total_costs_temp_ts, repair_costs_temp_ts, input_costs_temp_ts, desired_profit_ts, base_cost_ts))