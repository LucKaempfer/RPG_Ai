class WP:
    def __init__(self, name, lvl, ap, rap, map, dp, rdp, mdp, kg):
        self.name = name
        self.lvl = lvl
        self.ap = ap
        self.rap = rap
        self.map = map
        self.dp =dp
        self. rdp = rdp
        self.mdp = mdp
        self.kg = kg

    def effect(self):
        pass

class WP_melee_sharp(WP):
    def effect(self):
        #Inflict bleeding

class WP_melee_dull(WP):
    def effect(self):
        #Inflict Stun

class WP_range_sharp(WP):
    def effect(self):
        #inflict bleeding

class WP_range_dull(WP):
    def effect(self):
        #inflict Stun

class WP_magic_poison(WP):
    def effect(self):
        #inflict poison

class WP_magic_fire(WP):
    def effect(self):
        #inflict burning

class WP_magic_electric(WP):
    def effect(self):
        #inflict electrocuted

wp_melee_sharp_1 = [
    WP_melee_sharp('Saber', 1, 1, 0, 0, 1, 0, 0, 1),
    WP_melee_sharp('Spear', 1, 1, 0, 0, 1, 0, 0, 1),
    WP_melee_sharp('Dagger', 1, 1, 0, 1, 1, 0, 0, 1),
    WP_melee_sharp('Sword', 1, 1, 0, 0, 1, 0, 0, 1),
    WP_melee_sharp('Greatsword', 1, 1, 0, 0, 1, 0, 0, 1)]

wp_melee_dull_1 = [
    WP_melee_dull('Warhammer', 1, 1, 0, 0, 1, 0, 0, 1),
    WP_melee_dull('Mace', 1, 1, 0, 0, 1, 0, 0, 1),
    WP_melee_dull('Club', 1, 1, 0, 0, 1, 0, 0, 1)]

wp_range_sharp_1 = [
    WP_range_sharp('Crossbow', 1, 0, 1, 0, 0, 0, 0, 1, ),
    WP_range_sharp('Bow', 1, 0, 1, 0, 0, 0, 0, 1),
    WP_range_sharp('Blowpipe', 1, 0, 1, 0, 0, 0, 0, 1)]

wp_range_dull_1 = [
    WP_range_dull('Boomerang', 1, 0, 1, 0, 0, 0, 0, 1),
    WP_range_dull('Slingshot', 1, 0, 1, 0, 0, 0, 0, 1),
    WP_range_dull('Whip', 1, 0, 1, 0, 0, 0, 0, 1)]

wp_magic_poison_1 = [
    WP_magic_poison('Poisonous Staff', 1, 0, 0, 1, 0, 0, 0, 1),
    WP_magic_poison('Poisonous Wand', 1, 0, 0, 1, 0, 0, 0, 1)]

wp_magic_fire_1 = [
    WP_magic_poison('Fiery Staff', 1, 0, 0, 1, 0, 0, 0, 1),
    WP_magic_poison('Fiery Wand', 1, 0, 0, 1, 0, 0, 0, 1)]

wp_magic_electric_1 = [
    WP_magic_poison('Electric Staff', 1, 0, 0, 1, 0, 0, 0, 1),
    WP_magic_poison('Electric Wand', 1, 0, 0, 1, 0, 0, 0, 1)]

class Consumable:

class Armor:

class Trinket:

class Ability:

class Enemy:

class Boss:
