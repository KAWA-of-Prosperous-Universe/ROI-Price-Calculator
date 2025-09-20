
import urllib
import urllib.request
import os
import pickle
import json

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

def read_FIO_data(enable_cache = True):
    cache_file = "cache.pickle"
    if enable_cache and os.path.isfile(cache_file):
        with open(cache_file, 'rb') as file:
            print('reading pickle file')
            buildings, recipes, materials, planets = pickle.load(file)
    else:
        buildings = query_FNAR_REST_list('https://rest.fnar.net/building/allbuildings', 'Ticker')
        recipes = query_FNAR_REST_list('https://rest.fnar.net/recipes/allrecipes', 'StandardRecipeName')
        materials = query_FNAR_REST_list('https://rest.fnar.net/material/allmaterials', 'Ticker')
        planets = query_FNAR_REST_list('https://rest.fnar.net/planet/allplanets/full', 'PlanetNaturalId')
        if enable_cache:
            with open(cache_file, 'wb') as file:
                print('writing pickle file')
                pickle.dump([buildings, recipes, materials, planets], file)
    
    materials_byID = generate_materials_byID(materials)
    supplement_materials_with_recipes(materials, recipes)
    supplement_materials_with_natural_resource_planets(materials, planets, materials_byID)
    
    return buildings, recipes, materials, planets, materials_byID

def generate_materials_byID(materials):
    # create a list of materials that can be indexed by Material ID
    materials_byID = {}
    for material in materials.values():
        if material['MaterialId'] in materials_byID:
            print('Found duplicate material ID: %s'.format(material['MaterialId']))
        materials_byID[material['MaterialId']] = material['Ticker']
    
    return materials_byID

def supplement_materials_with_recipes(materials, recipes):
    # Add a list of recipes to each material indicating what recipes produce that material
    for recipe in recipes.values():
        for item in recipe['Outputs']:
            if item['Ticker'] in materials:
                if 'RecipeList' in materials[item['Ticker']]:
                    materials[item['Ticker']]['RecipeList'].append(recipe['StandardRecipeName'])
                else:
                    materials[item['Ticker']]['RecipeList'] = [recipe['StandardRecipeName']]
            else:
                print('recipe: {}, output: {}, not found in materials.'.format(recipe, item))

def supplement_materials_with_natural_resource_planets(materials, planets, materials_byID):
    # Add a list of planets to each material that produce that resource
    for planet in planets.values():
        for item in planet['Resources']:
            if item['MaterialId'] in materials_byID:
                if 'PlanetList' in materials[materials_byID[item['MaterialId']]]:
                    materials[materials_byID[item['MaterialId']]]['PlanetList'].append(planet['PlanetNaturalId'])
                else:
                    materials[materials_byID[item['MaterialId']]]['PlanetList'] = [planet['PlanetNaturalId']]
            else:
                print('planet: {}, resource: {}, not found in materials.'.format(planet, item))
