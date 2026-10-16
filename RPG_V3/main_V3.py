import sys
import pickle
from fileinput import close

global char_inventory
global char_equipment

#Dictionary for keeping track of the basic stats of the Character
char_stats ={
    'name' : '',
    'lvl' : 0,
    'xp' : 0,
    'max_xp' : 100,
    'hp' : 0,
    'ap' : 0,
    'rap' : 0,
    'map' : 0,
    'dp' : 0,
    'rdp' : 0,
    'mdp' : 0}

#Dictionary keeping track of all the not character based stats
lvl_up_stats ={
    'hp' : 0,
    'ap' : 0,
    'rap' : 0,
    'map' : 0,
    'dp' : 0,
    'rdp' : 0,
    'mdp' : 0}

def backpack():
    print(f'You are holding {weight} of {max_weight}\n_________________________________')
    #for item in char_inventory:


def inventory():
    input = input('What do you want to do in your inventory?')
    if  input == 'Backpack':
        backpack()
        inventory()


def xp_check():
    #Function checking if the current xp is enough to level up and if so doing the level up
    # Inputdata:
    # Outputdata:
    char_stats['max_xp'] = int(char_stats['lvl']) * 100
    if int(char_stats['xp']) > int(char_stats['max_xp']):
        print(f'LEVEL UP!\nXP needed to level up: {char_stats["max_xp"]}    Your XP: {char_stats["xp"]}')
        rest_xp = int(char_stats['xp']) - int(char_stats['max_xp'])
        char_stats['xp'] = rest_xp
        print(f'Please choose the attribute you want to level up:\nCurrent Stat     How many times it was already upgraded')
        print(f'HP: {char_stats["hp"]}    {lvl_up_stats["hp"]}\nAP: {char_stats["ap"]}    {lvl_up_stats["ap"]}RAP: {char_stats["rap"]}    {lvl_up_stats["rap"]}MAP: {char_stats["map"]}    {lvl_up_stats["map"]}DP: {char_stats["dp"]}    {lvl_up_stats["dp"]}RDP: {char_stats["rdp"]}    {lvl_up_stats["rdp"]}MDP: {char_stats["mdp"]}    {lvl_up_stats["mdp"]}')
        upgrader = input('What stat do you want to upgrade?')


        print(f'Your remaining XP: {char_stats["xp"]}')

def character_double_check(filename, name):
    with open(filename, 'r') as file:
        for line in file:
            if name in line:
                return True
    return False

def hero_maker():
    # Function for generating all needed Files for an Character an adding the Name to the list saved_chars
    # Inputdata: N/A
    # Outputdata: name.txt, name_hidden.txt, name_inventory.pkl, name_equipment.pkl, saved_chars.txt
    while True:
        name = input('What is the Name of your Hero?')
        open('saved_chars.txt', 'a').close()
        with open(f'saved_chars.txt', 'r') as file:
            double = False
            for line in file:
                if name in line:
                    double = True
                    break
        if double == True:
            print(name + ' already exists. Choose another name')
            continue
        choice = input('Is ' + name + ' correct?\nOptions: yes, no or exit')
        if choice == 'exit':
            while True:
                exit_choice = input('Do you want to leave the Game?\nOptions: yes or no')
                if exit_choice == 'yes':
                    sys.exit()
                elif exit_choice == 'no':
                    break
                else:
                    print(exit_choice + ' is not a known command. Please try again')
                    continue
        elif choice == 'no':
            continue
        elif choice == 'yes':
            break
    hero_file = open(f'{name}.txt', 'w')
    #NAME/LVL/XP/HP/AP/RAP/MAP/DP/RDP/MDP
    hero_file.write(name + '\n1\n0\n100\n5\n5\n5\n5\n5\n5').close()
    hidden_file = open(f'{name}_hidden.txt', 'w')
    #Remaining_XP/lvl_hp/lvl_ap/lvl_rap/lvl_map/lvl_dp/lvl_rdp/lvl_mdp
    hidden_file.write('100\n0\n0\n0\n0\n0\n0\n0\n0').close()
    inventory = open(f'{name}_inventory.pkl', 'w').close()
    with open(f'{name}_inventory.pkl', 'w') as inv:
        char_inventory = pickle.load(inv)
    equippment = open(f'{name}_equipment.pkl', 'w')
    equippment.close()
    with open(f'{name}_equipment.pkl', 'w') as eqmt:
        char_equipment = pickle.load(eqmt)
    eqmt.close()
    load_char = open(f'{name}.txt', 'r')
    char_stats['name'] = load_char.readline()
    char_stats['lvl'] = int(load_char.readline())
    char_stats['xp'] = int(load_char.readline())
    char_stats['hp'] = int(load_char.readline())
    char_stats['ap'] = int(load_char.readline())
    char_stats['rap'] = int(load_char.readline())
    char_stats['map'] = int(load_char.readline())
    char_stats['dp'] = int(load_char.readline())
    char_stats['rdp'] = int(load_char.readline())
    char_stats['mdp'] = int(load_char.readline())
    load_char.close()
    load_char_hidden = open(f'{name}_hidden.txt', 'r')
    char_stats['max_xp'] = int(load_char_hidden.readline())
    lvl_up_stats['hp'] = int(load_char_hidden.readline())
    lvl_up_stats['ap'] = int(load_char_hidden.readline())
    lvl_up_stats['rap'] = int(load_char_hidden.readline())
    lvl_up_stats['map'] = int(load_char_hidden.readline())
    lvl_up_stats['dp'] = int(load_char_hidden.readline())
    lvl_up_stats['rdp'] = int(load_char_hidden.readline())
    lvl_up_stats['mdp'] = int(load_char_hidden.readline())
    load_char_hidden.close()
    #Add basic gear to inventory
    print(f'{name} has been set up.')
    index_char = open('saved_chars.txt', 'a')
    index_char.write(char_stats['name'])
    index_char.close
    return

def hero_chooser():
    if x == y:
        print('H')


def tutorial():
    # Function wich handles the Tutorial at the Start of the Game
    # Inputdata: tutorial.txt
    # Outputdata: N/A
    while True:
        choice = input('Do you want an Tutorial?\nOptions: yes, no or exit')
        if choice == 'exit':
            while True:
                exit_choice = input('Do you want to leave the Game?\nOptions: yes or no')
                if exit_choice == 'yes':
                    sys.exit()
                elif exit_choice == 'no':
                    break
                else:
                    print(exit_choice + ' is not a known command. Please try again')
                    continue
        elif choice == 'yes':
            file = open('tutorial.txt', 'r')
            print(file.read())
            file.close()
            return
        elif choice == 'no':
            return
        else:
            print('Enter yes, no or exit')
            continue

def start():
    # Function wich handles the Start of the Game after the Tutorial
    # Inputdata: N/A
    # Outputdata: N/A
    while True:
        choice = input('New or Saved Hero?\nOptions: yes, no or exit')
        if choice == 'exit':
            while True:
                exit_choice = input('Do you want to leave the Game?\nOptions: yes or no')
                if exit_choice == 'yes':
                    sys.exit()
                elif exit_choice == 'no':
                    break
                else:
                    print(exit_choice + ' is not a known command. Please try again')
                    continue
        elif choice == 'new':
            hero_maker()
            return
        elif choice == 'saved':
            hero_chooser()
            return
        else:
            print('Enter yes, no or exit')
            continue

def lobby():
    while True:
        xp_check()
        base_input = input(f'Welcome in your Base {char_stats["name"].strip()}. What do you want to do?\nOptions: inventory')
        if base_input == 'inventory':
            inventory()
            continue


tutorial()

start()

lobby()
