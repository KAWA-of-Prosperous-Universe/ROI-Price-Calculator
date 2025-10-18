import sys
import json
import math
import KAWAUtils
# import numpy

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

def get_planet_build_requirements(planet):
    planet_specific_materials=[]
    for requirement in planet['BuildRequirements']:
        if requirement['MaterialTicker'] in ['LSE', 'TRU', 'PSL', 'LDE', 'LTA']:
            pass
        else:
            planet_specific_materials.append(requirement['MaterialTicker'])
    return planet_specific_materials

def get_recipe_output_from_material_type(material_type, factor, recipes):
    # https://pct.fnar.net/planet/
    if material_type == 'MINERAL':
        recipe_key = 'EXT:=>'
        output = 100*0.7*factor
    elif material_type == 'GASEOUS':
        recipe_key = 'COL:=>'
        output = 100*0.6*factor
    elif material_type == 'LIQUID':
        recipe_key = 'RIG:=>'
        output = 100*0.7*factor
    else:
        print('ERROR: unknown resource type: {}'.format(material_type))
    
    # convert from output/day to output/recipe run
    output = output * recipes[recipe_key]['TimeMs']/DAY_TIME_MS
    
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
        # Core Module is always needed
        building_list.append({'Ticker': 'CM', 'Count': 1})
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
    # Core Module is always needed
    building_list.append({'Ticker': 'CM', 'Count': 1})

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
                mat_build_quantity = 4*building['AreaCost']*building['Count']
            elif mat_ticker == 'AEF':
                mat_build_quantity = math.ceil(building['AreaCost']/3)*building['Count']
            elif mat_ticker == 'SEA':
                mat_build_quantity = 1*building['AreaCost']*building['Count']
            elif mat_ticker == 'INS':
                mat_build_quantity = 10*building['AreaCost']*building['Count']
            elif mat_ticker in ['HSE', 'TSH', 'BL', 'MGC']:
                mat_build_quantity = 1*building['Count']
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
    # read FIO data from the cache or retrieve the date from FIO and cache it.
    buildings, recipes, materials, planets, materials_byID = KAWAUtils.read_FIO_data()

    # create an "optimal" base setup for each building
    base_setups = {}
    for building in buildings.keys():
        base_list, building_count = calculate_single_building_base_setup(building, buildings)
        base_setups[building] = {'BaseList': base_list, 'BuildingCount': building_count}
    
    # Load the calulation options
    with open('ROICalculatorOptions.json', 'rt') as file:
        ROIOptions = json.load(file)

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
        if not ROIOptions['preferred_recipes'][material]:
            continue
        elif '=>' in ROIOptions['preferred_recipes'][material]:
            recipe = recipes[ROIOptions['preferred_recipes'][material]]
            output = 0
            for cur in recipe['Outputs']:
                if cur['Ticker'] == material:
                    output = cur['Amount']
                    # fudge output for NA
                    if material == 'NA':
                        output*=10
        else:
            planet = planets[ROIOptions['preferred_recipes'][material]]
            planet_specific_materials = get_planet_build_requirements(planet)
            materialinfo = {}
            for resource in planet['Resources']:
                if materials_byID[resource['MaterialId']] == material:
                    materialinfo = resource
                    materialinfo['Ticker'] = material
                    break
            if 'ResourceType' not in materialinfo:
                print('ERROR: {} not found.'.format(material))
            
            recipe_key, output = get_recipe_output_from_material_type(materialinfo['ResourceType'], materialinfo['Factor'], recipes)
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
            recipe_time = material_costs[material].Extras['recipe']['TimeMs']
            # adjust recipe time for fertility
            if material_costs[material].Extras['recipe']['BuildingTicker'] in ['FRM', 'ORC']:
                recipe_time *= ROIOptions['fertile_planet']['Fertility']/100
            input_costs_temp, repair_costs_temp, desired_profit_temp, total_costs_temp = calculate_total_cost(material, material_costs[material].Extras['output'], material_costs[material].Extras['recipe']['Inputs'], buildings[material_costs[material].Extras['recipe']['BuildingTicker']]['BuildingCosts'], recipe_time, buildings[material_costs[material].Extras['recipe']['BuildingTicker']]['AreaCost'], material_costs[material].Extras['planet_mats'], material_costs, input_costs, repair_costs, desired_profit, material_costs[material], base_setups[material_costs[material].Extras['recipe']['BuildingTicker']])
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
        
        if max_diff_elem['diff'] < 0.001:
            print('Iterations completed at n={}'.format(n))
            break

        print('Largest difference: {} {} ({}, {}, {}, {}, {})'.format(max_diff_elem['mat'], max_diff_elem['diff'], total_costs[max_diff_elem['mat']].Pioneer, total_costs[max_diff_elem['mat']].Settler, total_costs[max_diff_elem['mat']].Technician, total_costs[max_diff_elem['mat']].Engineer, total_costs[max_diff_elem['mat']].Scientist))

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

    # A = numpy.array([[Apio-1, Bpio, Cpio, Dpio, Epio],[Aset, Bset-1, Cset, Dset, Eset],[Atec, Btec, Ctec-1, Dtec, Etec],[Aeng, Beng, Ceng, Deng-1, Eeng],[Asci, Bsci, Csci, Dsci, Esci]])

    PIOc = SETc = TECc = ENGc = SCIc = 1e-7
    PIOc_target = 0.33e-7 # magic number that puts RAT at about current KAWA price
    previous = [PIOc, SETc, TECc, ENGc, SCIc]
    for n in range(100):
        PIOc = PIOc_target
        # PIOc = (            SETc*Bpio + TECc*Cpio + ENGc*Dpio + SCIc*Epio)/(1 - Apio)
        SETc = (PIOc*Aset +             TECc*Cset + ENGc*Dset + SCIc*Eset)/(1 - Bset)
        TECc = (PIOc*Atec + SETc*Btec +             ENGc*Dtec + SCIc*Etec)/(1 - Ctec)
        ENGc = (PIOc*Aeng + SETc*Beng + TECc*Ceng +             SCIc*Eeng)/(1 - Deng)
        SCIc = (PIOc*Asci + SETc*Bsci + TECc*Csci + ENGc*Dsci            )/(1 - Esci)
        print('PIO: {}, SET: {}, TEC: {}, ENG: {}, SCI: {}'.format(PIOc, SETc, TECc, ENGc, SCIc))
        current = [PIOc, SETc, TECc, ENGc, SCIc]
        print('PIOc initial = {}; PIOc current = {}'.format(PIOc, (SETc*Bpio + TECc*Cpio + ENGc*Dpio + SCIc*Epio)/(1 - Apio)))
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
        file.write('{},{},{},{},{},{}\n'.format('material', 'total cost', 'repair cost', 'input cost', 'desired profit', 'base unit cost'))
        for material in total_costs.keys():
            total_costs_ts[material] = total_costs[material].Pioneer*PIOc + total_costs[material].Settler*SETc + total_costs[material].Technician*TECc + total_costs[material].Engineer*ENGc + total_costs[material].Scientist*SCIc
            repair_costs_ts[material] = repair_costs[material].Pioneer*PIOc + repair_costs[material].Settler*SETc + repair_costs[material].Technician*TECc + repair_costs[material].Engineer*ENGc + repair_costs[material].Scientist*SCIc
            input_costs_ts[material] = input_costs[material].Pioneer*PIOc + input_costs[material].Settler*SETc + input_costs[material].Technician*TECc + input_costs[material].Engineer*ENGc + input_costs[material].Scientist*SCIc
            desired_profit_ts[material] = desired_profit[material].Pioneer*PIOc + desired_profit[material].Settler*SETc + desired_profit[material].Technician*TECc + desired_profit[material].Engineer*ENGc + desired_profit[material].Scientist*SCIc
            material_costs_ts[material] = material_costs[material].Pioneer*PIOc + material_costs[material].Settler*SETc + material_costs[material].Technician*TECc + material_costs[material].Engineer*ENGc + material_costs[material].Scientist*SCIc
            file.write('{},{},{},{},{},{}\n'.format(material, total_costs_ts[material], repair_costs_ts[material], input_costs_ts[material], desired_profit_ts[material], material_costs_ts[material]))
    
    # check ROI
    with open('ROI_check.csv', 'w') as file:
        file.write("material,ROI (days),net profit per day,build cost per day,gross income per day,repair costs per day,input costs per day,consumable costs per day\n")
        # consumable costs per day per 100 units of population
        pio_cost_check = 0
        for item in [{'mat':'COF','amount':0.5},{'mat':'DW','amount':4},{'mat':'RAT','amount':4},{'mat':'OVE','amount':0.5},{'mat':'PWO','amount':0.2}]:
            pio_cost_check = pio_cost_check + total_costs_ts[item['mat']]*item['amount']
        pio_cost_check /= 100
        set_cost_check = 0
        for item in [{'mat':'DW','amount':5},{'mat':'RAT','amount':6},{'mat':'KOM','amount':1},{'mat':'EXO','amount':0.5},{'mat':'REP','amount':0.2},{'mat':'PT','amount':0.5}]:
            set_cost_check = set_cost_check + total_costs_ts[item['mat']]*item['amount']
        set_cost_check /= 100
        tec_cost_check = 0
        for item in [{'mat':'DW','amount':7.5},{'mat':'RAT','amount':7},{'mat':'ALE','amount':1},{'mat':'MED','amount':0.5},{'mat':'SC','amount':0.1},{'mat':'HMS','amount':0.5},{'mat':'SCN','amount':0.1}]:
            tec_cost_check = tec_cost_check + total_costs_ts[item['mat']]*item['amount']
        tec_cost_check /= 100
        eng_cost_check = 0
        for item in [{'mat':'DW','amount':10},{'mat':'MED','amount':0.5},{'mat':'GIN','amount':1},{'mat':'FIM','amount':7},{'mat':'VG','amount':0.2},{'mat':'HSS','amount':0.2},{'mat':'PDA','amount':0.1}]:
            eng_cost_check = eng_cost_check + total_costs_ts[item['mat']]*item['amount']
        eng_cost_check /= 100
        sci_cost_check = 0
        for item in [{'mat':'DW','amount':10},{'mat':'MED','amount':0.5},{'mat':'WIN','amount':1},{'mat':'MEA','amount':7},{'mat':'NST','amount':0.1},{'mat':'LC','amount':0.2},{'mat':'WS','amount':0.1}]:
            sci_cost_check = sci_cost_check + total_costs_ts[item['mat']]*item['amount']
        sci_cost_check /= 100
        for material in total_costs_ts.keys():
            recipe = material_costs[material].Extras['recipe']
            output = material_costs[material].Extras['output']
            planet_specific_materials = material_costs[material].Extras['planet_mats']
            base_setup = base_setups[recipe['BuildingTicker']]
            building = buildings[recipe['BuildingTicker']]
            runs_per_day = DAY_TIME_MS / recipe['TimeMs']

            # Input material costs
            input_cost_check = 0
            for input_mat in recipe["Inputs"]:
                input_cost_check += input_mat['Amount']*total_costs_ts[input_mat['Ticker']]
            input_cost_check *= runs_per_day*base_setup['BuildingCount']

            # Population costs
            pop_cost_check = base_setup['BuildingCount']*(building['Pioneers']*pio_cost_check + building['Settlers']*set_cost_check + building['Technicians']*tec_cost_check + building['Engineers']*eng_cost_check + building['Scientists']*sci_cost_check)

            # Repair costs
            repair_cost_check = 0
            for cur_mat in buildings[building['Ticker']]['BuildingCosts']:
                repair_cost_check += base_setup['BuildingCount']*(total_costs_ts[cur_mat['CommodityTicker']]*math.ceil(cur_mat['Amount']*REPAIR_PERIOD_DAYS/180))
            for cur_mat in planet_specific_materials:
                mat_build_quantity = 1
                if cur_mat == 'MCG':
                    mat_build_quantity = 4*building['AreaCost']
                elif cur_mat == 'AEF':
                    mat_build_quantity = math.ceil(building['AreaCost']/3)
                elif cur_mat == 'SEA':
                    mat_build_quantity = 1*building['AreaCost']
                elif cur_mat == 'INS':
                    mat_build_quantity = 10*building['AreaCost']
                elif cur_mat in ['HSE', 'TSH', 'BL', 'MGC']:
                    mat_build_quantity = 1
                else:
                    print('ERROR: planet material not recognized: {}'.format(cur_mat))
                repair_cost_check += base_setup['BuildingCount']*(total_costs_ts[cur_mat]*math.ceil(mat_build_quantity*REPAIR_PERIOD_DAYS/180))
            repair_cost_check /= REPAIR_PERIOD_DAYS

            # Build costs
            build_cost_check = 0
            for cur_building in base_setup['BaseList']:
                for cur_mat in buildings[cur_building['Ticker']]['BuildingCosts']:
                    build_cost_check += cur_building['Count']*(total_costs_ts[cur_mat['CommodityTicker']]*cur_mat['Amount'])
                for cur_mat in planet_specific_materials:
                    mat_build_quantity = 1
                    if cur_mat == 'MCG':
                        mat_build_quantity = 4*cur_building['AreaCost']
                    elif cur_mat == 'AEF':
                        mat_build_quantity = math.ceil(cur_building['AreaCost']/3)
                    elif cur_mat == 'SEA':
                        mat_build_quantity = 1*cur_building['AreaCost']
                    elif cur_mat == 'INS':
                        mat_build_quantity = 10*cur_building['AreaCost']
                    elif cur_mat in ['HSE', 'TSH', 'BL', 'MGC']:
                        mat_build_quantity = 1
                    else:
                        print('ERROR: planet material not recognized: {}'.format(cur_mat))
                    build_cost_check += cur_building['Count']*(total_costs_ts[cur_mat]*mat_build_quantity)

            # Gross Profit
            gross_profit_check = 0
            if recipe["Outputs"]:
                for output_mat in recipe["Outputs"]:
                    gross_profit_check += output_mat['Amount']*total_costs_ts[output_mat['Ticker']]
            else:
                gross_profit_check += output*total_costs_ts[material]
            gross_profit_check *= runs_per_day*base_setup['BuildingCount']

            # Build cost / [Net profit per day (Gross Profit - Input material costs - repair costs - population costs)] = ROI
            net_profit_check = gross_profit_check - input_cost_check - repair_cost_check - pop_cost_check
            ROI_check = build_cost_check / net_profit_check
            file.write("{},{}{},{},{},{},{},{}\n".format(material, ROI_check, net_profit_check, build_cost_check, gross_profit_check, repair_cost_check, input_cost_check, pop_cost_check))

    with open('recipe_costs.csv', 'w') as file:
        file.write('{},{},{},{},{},{}\n'.format('recipe', 'total cost', 'repair cost', 'input cost', 'desired profit', 'base recipe cost'))
        planet_mats = ['MCG']
        for recipe in recipes.values():
            if not recipe['Outputs']:
                continue
            recipe_time = recipe['TimeMs']
            # adjust recipe time for fertility
            if recipe['BuildingTicker'] in ['FRM', 'ORC']:
                recipe_time *= ROIOptions['fertile_planet']['Fertility']/100
            building = buildings[recipe['BuildingTicker']]
            recipe_cost = calculate_population_cost(1, building, recipe_time)
            input_costs_temp, repair_costs_temp, desired_profit_temp, total_costs_temp = calculate_total_cost('', 1, recipe['Inputs'], building['BuildingCosts'], recipe['TimeMs'], building['AreaCost'], planet_mats, material_costs, input_costs, repair_costs, desired_profit, recipe_cost, base_setups[recipe['BuildingTicker']], False)

            total_costs_temp_ts = total_costs_temp.Pioneer*PIOc + total_costs_temp.Settler*SETc + total_costs_temp.Technician*TECc + total_costs_temp.Engineer*ENGc + total_costs_temp.Scientist*SCIc
            repair_costs_temp_ts = repair_costs_temp.Pioneer*PIOc + repair_costs_temp.Settler*SETc + repair_costs_temp.Technician*TECc + repair_costs_temp.Engineer*ENGc + repair_costs_temp.Scientist*SCIc
            input_costs_temp_ts = input_costs_temp.Pioneer*PIOc + input_costs_temp.Settler*SETc + input_costs_temp.Technician*TECc + input_costs_temp.Engineer*ENGc + input_costs_temp.Scientist*SCIc
            desired_profit_ts = desired_profit_temp.Pioneer*PIOc + desired_profit_temp.Settler*SETc + desired_profit_temp.Technician*TECc + desired_profit_temp.Engineer*ENGc + desired_profit_temp.Scientist*SCIc
            recipe_cost_ts = recipe_cost.Pioneer*PIOc + recipe_cost.Settler*SETc + recipe_cost.Technician*TECc + recipe_cost.Engineer*ENGc + recipe_cost.Scientist*SCIc
            file.write('{},{},{},{},{},{}\n'.format(recipe['StandardRecipeName'], total_costs_temp_ts, repair_costs_temp_ts, input_costs_temp_ts, desired_profit_ts, recipe_cost_ts))
    
    with open('natural_resource_costs.csv','w') as file:
        file.write('{},{},{},{},{},{},{}\n'.format('planet', 'material', 'total cost', 'repair cost', 'input cost', 'desired profit', 'base recipe cost'))
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
                recipe_key, output = get_recipe_output_from_material_type(item['ResourceType'], item['Factor'], recipes)
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
                file.write('{},{},{},{},{},{},{}\n'.format(planet['PlanetNaturalId'], material_ticker, total_costs_temp_ts, repair_costs_temp_ts, input_costs_temp_ts, desired_profit_ts, base_cost_ts))