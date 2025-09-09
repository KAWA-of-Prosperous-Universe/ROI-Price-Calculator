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
    desired_profit = {'PIONEER':0,'SETTLER':0,'TECHNICIAN':0,'ENGINEER':0,'SCIENTIST':0}
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
            desired_profit['PIONEER'] = desired_profit['PIONEER'] + recipe_time_fraction/base_output_per_run*mat_build_quantity*(base_cost_list[mat_ticker]['PIONEER'] + input_cost_cur['PIONEER'] + repair_cost_cur['PIONEER'] + desired_profit_cur['PIONEER'])
            desired_profit['SETTLER'] = desired_profit['SETTLER'] + recipe_time_fraction/base_output_per_run*mat_build_quantity*(base_cost_list[mat_ticker]['SETTLER'] + input_cost_cur['SETTLER'] + repair_cost_cur['SETTLER'] + desired_profit_cur['SETTLER'])
            desired_profit['TECHNICIAN'] = desired_profit['TECHNICIAN'] + recipe_time_fraction/base_output_per_run*mat_build_quantity*(base_cost_list[mat_ticker]['TECHNICIAN'] + input_cost_cur['TECHNICIAN'] + repair_cost_cur['TECHNICIAN'] + desired_profit_cur['TECHNICIAN'])
            desired_profit['ENGINEER'] = desired_profit['ENGINEER'] + recipe_time_fraction/base_output_per_run*mat_build_quantity*(base_cost_list[mat_ticker]['ENGINEER'] + input_cost_cur['ENGINEER'] + repair_cost_cur['ENGINEER'] + desired_profit_cur['ENGINEER'])
            desired_profit['SCIENTIST'] = desired_profit['SCIENTIST'] + recipe_time_fraction/base_output_per_run*mat_build_quantity*(base_cost_list[mat_ticker]['SCIENTIST'] + input_cost_cur['SCIENTIST'] + repair_cost_cur['SCIENTIST'] + desired_profit_cur['SCIENTIST'])
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
            desired_profit['PIONEER'] = desired_profit['PIONEER'] + recipe_time_fraction/base_output_per_run*mat_build_quantity*(base_cost_list[mat_ticker]['PIONEER'] + input_cost_cur['PIONEER'] + repair_cost_cur['PIONEER'] + desired_profit_cur['PIONEER'])
            desired_profit['SETTLER'] = desired_profit['SETTLER'] + recipe_time_fraction/base_output_per_run*mat_build_quantity*(base_cost_list[mat_ticker]['SETTLER'] + input_cost_cur['SETTLER'] + repair_cost_cur['SETTLER'] + desired_profit_cur['SETTLER'])
            desired_profit['TECHNICIAN'] = desired_profit['TECHNICIAN'] + recipe_time_fraction/base_output_per_run*mat_build_quantity*(base_cost_list[mat_ticker]['TECHNICIAN'] + input_cost_cur['TECHNICIAN'] + repair_cost_cur['TECHNICIAN'] + desired_profit_cur['TECHNICIAN'])
            desired_profit['ENGINEER'] = desired_profit['ENGINEER'] + recipe_time_fraction/base_output_per_run*mat_build_quantity*(base_cost_list[mat_ticker]['ENGINEER'] + input_cost_cur['ENGINEER'] + repair_cost_cur['ENGINEER'] + desired_profit_cur['ENGINEER'])
            desired_profit['SCIENTIST'] = desired_profit['SCIENTIST'] + recipe_time_fraction/base_output_per_run*mat_build_quantity*(base_cost_list[mat_ticker]['SCIENTIST'] + input_cost_cur['SCIENTIST'] + repair_cost_cur['SCIENTIST'] + desired_profit_cur['SCIENTIST'])
    
    return desired_profit

def calculate_population_cost(output_count, building, recipe_time):
    # Calculate population costs
    time_quant_factor = recipe_time/output_count
    population_cost = {'PIONEER':building['Pioneers']*time_quant_factor,'SETTLER':building['Settlers']*time_quant_factor,'TECHNICIAN':building['Technicians']*time_quant_factor,'ENGINEER':building['Engineers']*time_quant_factor,'SCIENTIST':building['Scientists']*time_quant_factor}
    return population_cost

def calculate_input_cost(cur_material, output_count, inputs, base_cost_list, input_cost_list, repair_cost_list, desired_profit_list, use_cur_material_costs = True):
    # Calculate input costs
    input_costs = {'PIONEER':0,'SETTLER':0,'TECHNICIAN':0,'ENGINEER':0,'SCIENTIST':0}
    for input_mat in inputs:
        mat_ticker = input_mat['Ticker']
        if use_cur_material_costs and mat_ticker == cur_material:
            input_cost_cur = input_costs
        else:
            input_cost_cur = input_cost_list[mat_ticker]
        input_costs['PIONEER'] = input_costs['PIONEER'] + input_mat['Amount']/output_count*(base_cost_list[mat_ticker]['PIONEER'] + input_cost_cur['PIONEER'] + repair_cost_list[mat_ticker]['PIONEER'] + desired_profit_list[mat_ticker]['PIONEER'])
        input_costs['SETTLER'] = input_costs['SETTLER'] + input_mat['Amount']/output_count*(base_cost_list[mat_ticker]['SETTLER'] + input_cost_cur['SETTLER'] + repair_cost_list[mat_ticker]['SETTLER'] + desired_profit_list[mat_ticker]['SETTLER'])
        input_costs['TECHNICIAN'] = input_costs['TECHNICIAN'] + input_mat['Amount']/output_count*(base_cost_list[mat_ticker]['TECHNICIAN'] + input_cost_cur['TECHNICIAN'] + repair_cost_list[mat_ticker]['TECHNICIAN'] + desired_profit_list[mat_ticker]['TECHNICIAN'])
        input_costs['ENGINEER'] = input_costs['ENGINEER'] + input_mat['Amount']/output_count*(base_cost_list[mat_ticker]['ENGINEER'] + input_cost_cur['ENGINEER'] + repair_cost_list[mat_ticker]['ENGINEER'] + desired_profit_list[mat_ticker]['ENGINEER'])
        input_costs['SCIENTIST'] = input_costs['SCIENTIST'] + input_mat['Amount']/output_count*(base_cost_list[mat_ticker]['SCIENTIST'] + input_cost_cur['SCIENTIST'] + repair_cost_list[mat_ticker]['SCIENTIST'] + desired_profit_list[mat_ticker]['SCIENTIST'])
    
    return input_costs

def calculate_repair_cost(cur_material, output_count, building_costs, input_costs, recipe_time, building_area_cost, planet_mats, base_cost_list, input_cost_list, repair_cost_list, desired_profit_list, use_cur_material_costs = True):
    # Add repair costs
    repair_material_fraction = REPAIR_PERIOD_DAYS/180 # fraction of repair materials needed due to repair time
    recipe_time_fraction = recipe_time/REPAIR_PERIOD_MS # fraction of repair materials needed for each recipe run
    repair_costs = {'PIONEER':0,'SETTLER':0,'TECHNICIAN':0,'ENGINEER':0,'SCIENTIST':0}
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
        repair_costs['PIONEER'] = repair_costs['PIONEER'] + recipe_time_fraction/output_count*mat_repair_quantity*(base_cost_list[mat_ticker]['PIONEER'] + input_cost_cur['PIONEER'] + repair_cost_cur['PIONEER'] + desired_profit_list[mat_ticker]['PIONEER'])
        repair_costs['SETTLER'] = repair_costs['SETTLER'] + recipe_time_fraction/output_count*mat_repair_quantity*(base_cost_list[mat_ticker]['SETTLER'] + input_cost_cur['SETTLER'] + repair_cost_cur['SETTLER'] + desired_profit_list[mat_ticker]['SETTLER'])
        repair_costs['TECHNICIAN'] = repair_costs['TECHNICIAN'] + recipe_time_fraction/output_count*mat_repair_quantity*(base_cost_list[mat_ticker]['TECHNICIAN'] + input_cost_cur['TECHNICIAN'] + repair_cost_cur['TECHNICIAN'] + desired_profit_list[mat_ticker]['TECHNICIAN'])
        repair_costs['ENGINEER'] = repair_costs['ENGINEER'] + recipe_time_fraction/output_count*mat_repair_quantity*(base_cost_list[mat_ticker]['ENGINEER'] + input_cost_cur['ENGINEER'] + repair_cost_cur['ENGINEER'] + desired_profit_list[mat_ticker]['ENGINEER'])
        repair_costs['SCIENTIST'] = repair_costs['SCIENTIST'] + recipe_time_fraction/output_count*mat_repair_quantity*(base_cost_list[mat_ticker]['SCIENTIST'] + input_cost_cur['SCIENTIST'] + repair_cost_cur['SCIENTIST'] + desired_profit_list[mat_ticker]['SCIENTIST'])
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
        repair_costs['PIONEER'] = repair_costs['PIONEER'] + recipe_time_fraction/output_count*mat_repair_quantity*(base_cost_list[mat_ticker]['PIONEER'] + input_cost_cur['PIONEER'] + repair_cost_cur['PIONEER'] + desired_profit_list[mat_ticker]['PIONEER'])
        repair_costs['SETTLER'] = repair_costs['SETTLER'] + recipe_time_fraction/output_count*mat_repair_quantity*(base_cost_list[mat_ticker]['SETTLER'] + input_cost_cur['SETTLER'] + repair_cost_cur['SETTLER'] + desired_profit_list[mat_ticker]['SETTLER'])
        repair_costs['TECHNICIAN'] = repair_costs['TECHNICIAN'] + recipe_time_fraction/output_count*mat_repair_quantity*(base_cost_list[mat_ticker]['TECHNICIAN'] + input_cost_cur['TECHNICIAN'] + repair_cost_cur['TECHNICIAN'] + desired_profit_list[mat_ticker]['TECHNICIAN'])
        repair_costs['ENGINEER'] = repair_costs['ENGINEER'] + recipe_time_fraction/output_count*mat_repair_quantity*(base_cost_list[mat_ticker]['ENGINEER'] + input_cost_cur['ENGINEER'] + repair_cost_cur['ENGINEER'] + desired_profit_list[mat_ticker]['ENGINEER'])
        repair_costs['SCIENTIST'] = repair_costs['SCIENTIST'] + recipe_time_fraction/output_count*mat_repair_quantity*(base_cost_list[mat_ticker]['SCIENTIST'] + input_cost_cur['SCIENTIST'] + repair_cost_cur['SCIENTIST'] + desired_profit_list[mat_ticker]['SCIENTIST'])
    
    return repair_costs

def calculate_total_cost(cur_material, output_count, inputs, building_costs, recipe_time, building_area_cost, planet_mats, base_cost_list, input_cost_list, repair_cost_list, desired_profit_list, base_cost, base_setup, use_cur_material_costs = True):
    input_costs = calculate_input_cost(cur_material, output_count, inputs, base_cost_list, input_cost_list, repair_cost_list, desired_profit_list, use_cur_material_costs)
    
    repair_costs = calculate_repair_cost(cur_material, output_count, building_costs, input_costs, recipe_time, building_area_cost, planet_mats, base_cost_list, input_cost_list, repair_cost_list, desired_profit_list, use_cur_material_costs)

    desired_profit = calculate_desired_profit(cur_material, output_count, input_costs, repair_costs, recipe_time, planet_mats, base_cost_list, input_cost_list, repair_cost_list, desired_profit_list, base_setup, use_cur_material_costs)

    # calculate total costs
    total_costs = {'PIONEER':0,'SETTLER':0,'TECHNICIAN':0,'ENGINEER':0,'SCIENTIST':0}
    # if desired_profit['PIONEER'] > base_cost['PIONEER'] + input_costs['PIONEER'] + repair_costs['PIONEER']:
    #     desired_profit['PIONEER'] = base_cost['PIONEER'] + input_costs['PIONEER'] + repair_costs['PIONEER']
    total_costs['PIONEER'] = base_cost['PIONEER'] + input_costs['PIONEER'] + repair_costs['PIONEER'] + desired_profit['PIONEER']
    # if desired_profit['SETTLER'] > base_cost['SETTLER'] + input_costs['SETTLER'] + repair_costs['SETTLER']:
    #     desired_profit['SETTLER'] = base_cost['SETTLER'] + input_costs['SETTLER'] + repair_costs['SETTLER']
    total_costs['SETTLER'] = base_cost['SETTLER'] + input_costs['SETTLER'] + repair_costs['SETTLER'] + desired_profit['SETTLER']
    # if desired_profit['TECHNICIAN'] > base_cost['TECHNICIAN'] + input_costs['TECHNICIAN'] + repair_costs['TECHNICIAN']:
    #     desired_profit['TECHNICIAN'] = base_cost['TECHNICIAN'] + input_costs['TECHNICIAN'] + repair_costs['TECHNICIAN']
    total_costs['TECHNICIAN'] = base_cost['TECHNICIAN'] + input_costs['TECHNICIAN'] + repair_costs['TECHNICIAN'] + desired_profit['TECHNICIAN']
    # if desired_profit['ENGINEER'] > base_cost['ENGINEER'] + input_costs['ENGINEER'] + repair_costs['ENGINEER']:
    #     desired_profit['ENGINEER'] = base_cost['ENGINEER'] + input_costs['ENGINEER'] + repair_costs['ENGINEER']
    total_costs['ENGINEER'] = base_cost['ENGINEER'] + input_costs['ENGINEER'] + repair_costs['ENGINEER'] + desired_profit['ENGINEER']
    # if desired_profit['SCIENTIST'] > base_cost['SCIENTIST'] + input_costs['SCIENTIST'] + repair_costs['SCIENTIST']:
    #     desired_profit['SCIENTIST'] = base_cost['SCIENTIST'] + input_costs['SCIENTIST'] + repair_costs['SCIENTIST']
    total_costs['SCIENTIST'] = base_cost['SCIENTIST'] + input_costs['SCIENTIST'] + repair_costs['SCIENTIST'] + desired_profit['SCIENTIST']
    
    return input_costs, repair_costs, desired_profit, total_costs

if __name__ == '__main__':
    args = sys.argv[1:]
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
        material_costs[material]['recipe'] = recipe
        material_costs[material]['output'] = output
        material_costs[material]['planet_mats'] = planet_specific_materials
        input_costs[material] = {'PIONEER':0,'SETTLER':0,'TECHNICIAN':0,'ENGINEER':0,'SCIENTIST':0}
        repair_costs[material] = {'PIONEER':0,'SETTLER':0,'TECHNICIAN':0,'ENGINEER':0,'SCIENTIST':0}
        desired_profit[material] = {'PIONEER':0,'SETTLER':0,'TECHNICIAN':0,'ENGINEER':0,'SCIENTIST':0}
        total_costs[material] = {'PIONEER':0,'SETTLER':0,'TECHNICIAN':0,'ENGINEER':0,'SCIENTIST':0}

    # iterate over materials to find final cost
    for n in range(100):
        max_diff_elem = {'diff':-1, 'mat':''}
        for material in material_costs.keys():
            
            input_costs_temp, repair_costs_temp, desired_profit_temp, total_costs_temp = calculate_total_cost(material, material_costs[material]['output'], material_costs[material]['recipe']['Inputs'], buildings[material_costs[material]['recipe']['BuildingTicker']]['BuildingCosts'], material_costs[material]['recipe']['TimeMs'], buildings[material_costs[material]['recipe']['BuildingTicker']]['AreaCost'], material_costs[material]['planet_mats'], material_costs, input_costs, repair_costs, desired_profit, material_costs[material], base_setups[material_costs[material]['recipe']['BuildingTicker']])
            pioneers_diff = total_costs_temp['PIONEER'] - total_costs[material]['PIONEER']
            setttlers_diff = total_costs_temp['SETTLER'] - total_costs[material]['SETTLER']
            technicians_diff = total_costs_temp['TECHNICIAN'] - total_costs[material]['TECHNICIAN']
            engineers_diff = total_costs_temp['ENGINEER'] - total_costs[material]['ENGINEER']
            scientists_diff = total_costs_temp['SCIENTIST'] - total_costs[material]['SCIENTIST']
            diff_sum = pioneers_diff+setttlers_diff+technicians_diff+engineers_diff+scientists_diff
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
        print('Largest difference: {} {} ({}, {}, {}, {}, {})'.format(max_diff_elem['mat'], max_diff_elem['diff'], total_costs[max_diff_elem['mat']]['PIONEER'], total_costs[max_diff_elem['mat']]['SETTLER'], total_costs[max_diff_elem['mat']]['TECHNICIAN'], total_costs[max_diff_elem['mat']]['ENGINEER'], total_costs[max_diff_elem['mat']]['SCIENTIST']))
        if max_diff_elem['diff'] < 0.001:
            print('Iterations completed at n={}'.format(n))
            break

    # Cost all recipes based on the selected material recipes
    

    # calculate costs for workers
    PIO = {'PIONEER':0,'SETTLER':0,'TECHNICIAN':0,'ENGINEER':0,'SCIENTIST':0}
    SET = {'PIONEER':0,'SETTLER':0,'TECHNICIAN':0,'ENGINEER':0,'SCIENTIST':0}
    TEC = {'PIONEER':0,'SETTLER':0,'TECHNICIAN':0,'ENGINEER':0,'SCIENTIST':0}
    ENG = {'PIONEER':0,'SETTLER':0,'TECHNICIAN':0,'ENGINEER':0,'SCIENTIST':0}
    SCI = {'PIONEER':0,'SETTLER':0,'TECHNICIAN':0,'ENGINEER':0,'SCIENTIST':0}
    # consumable costs per day per 100 units of population
    for item in [{'mat':'COF','amount':0.5},{'mat':'DW','amount':4},{'mat':'RAT','amount':4},{'mat':'OVE','amount':0.5},{'mat':'PWO','amount':0.2}]:
        PIO['PIONEER'] = PIO['PIONEER'] + total_costs[item['mat']]['PIONEER']*item['amount']
        PIO['SETTLER'] = PIO['SETTLER'] + total_costs[item['mat']]['SETTLER']*item['amount']
        PIO['TECHNICIAN'] = PIO['TECHNICIAN'] + total_costs[item['mat']]['TECHNICIAN']*item['amount']
        PIO['ENGINEER'] = PIO['ENGINEER'] + total_costs[item['mat']]['ENGINEER']*item['amount']
        PIO['SCIENTIST'] = PIO['SCIENTIST'] + total_costs[item['mat']]['SCIENTIST']*item['amount']
    for item in [{'mat':'DW','amount':5},{'mat':'RAT','amount':6},{'mat':'KOM','amount':1},{'mat':'EXO','amount':0.5},{'mat':'REP','amount':0.2},{'mat':'PT','amount':0.5}]:
        SET['PIONEER'] = SET['PIONEER'] + total_costs[item['mat']]['PIONEER']*item['amount']
        SET['SETTLER'] = SET['SETTLER'] + total_costs[item['mat']]['SETTLER']*item['amount']
        SET['TECHNICIAN'] = SET['TECHNICIAN'] + total_costs[item['mat']]['TECHNICIAN']*item['amount']
        SET['ENGINEER'] = SET['ENGINEER'] + total_costs[item['mat']]['ENGINEER']*item['amount']
        SET['SCIENTIST'] = SET['SCIENTIST'] + total_costs[item['mat']]['SCIENTIST']*item['amount']
    for item in [{'mat':'DW','amount':7.5},{'mat':'RAT','amount':7},{'mat':'ALE','amount':1},{'mat':'MED','amount':0.5},{'mat':'SC','amount':0.1},{'mat':'HMS','amount':0.5},{'mat':'SCN','amount':0.1}]:
        TEC['PIONEER'] = TEC['PIONEER'] + total_costs[item['mat']]['PIONEER']*item['amount']
        TEC['SETTLER'] = TEC['SETTLER'] + total_costs[item['mat']]['SETTLER']*item['amount']
        TEC['TECHNICIAN'] = TEC['TECHNICIAN'] + total_costs[item['mat']]['TECHNICIAN']*item['amount']
        TEC['ENGINEER'] = TEC['ENGINEER'] + total_costs[item['mat']]['ENGINEER']*item['amount']
        TEC['SCIENTIST'] = TEC['SCIENTIST'] + total_costs[item['mat']]['SCIENTIST']*item['amount']
    for item in [{'mat':'DW','amount':10},{'mat':'MED','amount':0.5},{'mat':'GIN','amount':1},{'mat':'FIM','amount':7},{'mat':'VG','amount':0.2},{'mat':'HSS','amount':0.2},{'mat':'PDA','amount':0.1}]:
        ENG['PIONEER'] = ENG['PIONEER'] + total_costs[item['mat']]['PIONEER']*item['amount']
        ENG['SETTLER'] = ENG['SETTLER'] + total_costs[item['mat']]['SETTLER']*item['amount']
        ENG['TECHNICIAN'] = ENG['TECHNICIAN'] + total_costs[item['mat']]['TECHNICIAN']*item['amount']
        ENG['ENGINEER'] = ENG['ENGINEER'] + total_costs[item['mat']]['ENGINEER']*item['amount']
        ENG['SCIENTIST'] = ENG['SCIENTIST'] + total_costs[item['mat']]['SCIENTIST']*item['amount']
    for item in [{'mat':'DW','amount':10},{'mat':'MED','amount':0.5},{'mat':'WIN','amount':1},{'mat':'MEA','amount':7},{'mat':'NST','amount':0.1},{'mat':'LC','amount':0.2},{'mat':'WS','amount':0.1}]:
        SCI['PIONEER'] = SCI['PIONEER'] + total_costs[item['mat']]['PIONEER']*item['amount']
        SCI['SETTLER'] = SCI['SETTLER'] + total_costs[item['mat']]['SETTLER']*item['amount']
        SCI['TECHNICIAN'] = SCI['TECHNICIAN'] + total_costs[item['mat']]['TECHNICIAN']*item['amount']
        SCI['ENGINEER'] = SCI['ENGINEER'] + total_costs[item['mat']]['ENGINEER']*item['amount']
        SCI['SCIENTIST'] = SCI['SCIENTIST'] + total_costs[item['mat']]['SCIENTIST']*item['amount']
    
    # scale to 1 unit of population per ms.
    Apio = PIO['PIONEER']/100/DAY_TIME_MS
    Bpio = PIO['SETTLER']/100/DAY_TIME_MS
    Cpio = PIO['TECHNICIAN']/100/DAY_TIME_MS
    Dpio = PIO['ENGINEER']/100/DAY_TIME_MS
    Epio = PIO['SCIENTIST']/100/DAY_TIME_MS
    
    Aset = SET['PIONEER']/100/DAY_TIME_MS
    Bset = SET['SETTLER']/100/DAY_TIME_MS
    Cset = SET['TECHNICIAN']/100/DAY_TIME_MS
    Dset = SET['ENGINEER']/100/DAY_TIME_MS
    Eset = SET['SCIENTIST']/100/DAY_TIME_MS
    
    Atec = TEC['PIONEER']/100/DAY_TIME_MS
    Btec = TEC['SETTLER']/100/DAY_TIME_MS
    Ctec = TEC['TECHNICIAN']/100/DAY_TIME_MS
    Dtec = TEC['ENGINEER']/100/DAY_TIME_MS
    Etec = TEC['SCIENTIST']/100/DAY_TIME_MS
    
    Aeng = ENG['PIONEER']/100/DAY_TIME_MS
    Beng = ENG['SETTLER']/100/DAY_TIME_MS
    Ceng = ENG['TECHNICIAN']/100/DAY_TIME_MS
    Deng = ENG['ENGINEER']/100/DAY_TIME_MS
    Eeng = ENG['SCIENTIST']/100/DAY_TIME_MS
    
    Asci = SCI['PIONEER']/100/DAY_TIME_MS
    Bsci = SCI['SETTLER']/100/DAY_TIME_MS
    Csci = SCI['TECHNICIAN']/100/DAY_TIME_MS
    Dsci = SCI['ENGINEER']/100/DAY_TIME_MS
    Esci = SCI['SCIENTIST']/100/DAY_TIME_MS

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
            total_costs_ts[material] = total_costs[material]['PIONEER']*PIOc + total_costs[material]['SETTLER']*SETc + total_costs[material]['TECHNICIAN']*TECc + total_costs[material]['ENGINEER']*ENGc + total_costs[material]['SCIENTIST']*SCIc
            repair_costs_ts[material] = repair_costs[material]['PIONEER']*PIOc + repair_costs[material]['SETTLER']*SETc + repair_costs[material]['TECHNICIAN']*TECc + repair_costs[material]['ENGINEER']*ENGc + repair_costs[material]['SCIENTIST']*SCIc
            input_costs_ts[material] = input_costs[material]['PIONEER']*PIOc + input_costs[material]['SETTLER']*SETc + input_costs[material]['TECHNICIAN']*TECc + input_costs[material]['ENGINEER']*ENGc + input_costs[material]['SCIENTIST']*SCIc
            desired_profit_ts[material] = desired_profit[material]['PIONEER']*PIOc + desired_profit[material]['SETTLER']*SETc + desired_profit[material]['TECHNICIAN']*TECc + desired_profit[material]['ENGINEER']*ENGc + desired_profit[material]['SCIENTIST']*SCIc
            material_costs_ts[material] = material_costs[material]['PIONEER']*PIOc + material_costs[material]['SETTLER']*SETc + material_costs[material]['TECHNICIAN']*TECc + material_costs[material]['ENGINEER']*ENGc + material_costs[material]['SCIENTIST']*SCIc
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

            total_costs_temp_ts = total_costs_temp['PIONEER']*PIOc + total_costs_temp['SETTLER']*SETc + total_costs_temp['TECHNICIAN']*TECc + total_costs_temp['ENGINEER']*ENGc + total_costs_temp['SCIENTIST']*SCIc
            repair_costs_temp_ts = repair_costs_temp['PIONEER']*PIOc + repair_costs_temp['SETTLER']*SETc + repair_costs_temp['TECHNICIAN']*TECc + repair_costs_temp['ENGINEER']*ENGc + repair_costs_temp['SCIENTIST']*SCIc
            input_costs_temp_ts = input_costs_temp['PIONEER']*PIOc + input_costs_temp['SETTLER']*SETc + input_costs_temp['TECHNICIAN']*TECc + input_costs_temp['ENGINEER']*ENGc + input_costs_temp['SCIENTIST']*SCIc
            desired_profit_ts = desired_profit_temp['PIONEER']*PIOc + desired_profit_temp['SETTLER']*SETc + desired_profit_temp['TECHNICIAN']*TECc + desired_profit_temp['ENGINEER']*ENGc + desired_profit_temp['SCIENTIST']*SCIc
            recipe_cost_ts = recipe_cost['PIONEER']*PIOc + recipe_cost['SETTLER']*SETc + recipe_cost['TECHNICIAN']*TECc + recipe_cost['ENGINEER']*ENGc + recipe_cost['SCIENTIST']*SCIc
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
                base_cost['PIONEER'] = natural_resource_building_cost[recipe_key]['PIONEER']/output
                base_cost['SETTLER'] = natural_resource_building_cost[recipe_key]['SETTLER']/output
                base_cost['TECHNICIAN'] = natural_resource_building_cost[recipe_key]['TECHNICIAN']/output
                base_cost['ENGINEER'] = natural_resource_building_cost[recipe_key]['ENGINEER']/output
                base_cost['SCIENTIST'] = natural_resource_building_cost[recipe_key]['SCIENTIST']/output
                
                input_costs_temp, repair_costs_temp, desired_profit_temp, total_costs_temp = calculate_total_cost('', output, recipe['Inputs'], building['BuildingCosts'], recipe['TimeMs'], building['AreaCost'], planet_specific_materials, material_costs, input_costs, repair_costs, desired_profit, base_cost, base_setups[recipe['BuildingTicker']], False)

                total_costs_temp_ts = total_costs_temp['PIONEER']*PIOc + total_costs_temp['SETTLER']*SETc + total_costs_temp['TECHNICIAN']*TECc + total_costs_temp['ENGINEER']*ENGc + total_costs_temp['SCIENTIST']*SCIc
                repair_costs_temp_ts = repair_costs_temp['PIONEER']*PIOc + repair_costs_temp['SETTLER']*SETc + repair_costs_temp['TECHNICIAN']*TECc + repair_costs_temp['ENGINEER']*ENGc + repair_costs_temp['SCIENTIST']*SCIc
                input_costs_temp_ts = input_costs_temp['PIONEER']*PIOc + input_costs_temp['SETTLER']*SETc + input_costs_temp['TECHNICIAN']*TECc + input_costs_temp['ENGINEER']*ENGc + input_costs_temp['SCIENTIST']*SCIc
                desired_profit_temp_ts = desired_profit_temp['PIONEER']*PIOc + desired_profit_temp['SETTLER']*SETc + desired_profit_temp['TECHNICIAN']*TECc + desired_profit_temp['ENGINEER']*ENGc + desired_profit_temp['SCIENTIST']*SCIc
                base_cost_ts = base_cost['PIONEER']*PIOc + base_cost['SETTLER']*SETc + base_cost['TECHNICIAN']*TECc + base_cost['ENGINEER']*ENGc + base_cost['SCIENTIST']*SCIc
                file.write('{}, {}, {}, {}, {}, {}, {}\n'.format(planet['PlanetNaturalId'], material_ticker, total_costs_temp_ts, repair_costs_temp_ts, input_costs_temp_ts, desired_profit_ts, base_cost_ts))