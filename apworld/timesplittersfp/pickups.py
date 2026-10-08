"""Health and armour pickup spots per story mission -- generated from the level files
and recorded play-throughs; do not edit by hand.

Per mission, a list of spots:
    (n, kind, war_indices, difficulties, (x, y, z), needs, extra, container)
n            index within the mission in route order (listed spots 0.., containers 0..)
kind         "Health" or "Armour"
war_indices  the level's .war item records at this spot (an Easy record and its
             Normal/Hard twin share one placement node); () for a container
difficulties where the pickup appears
(x, y, z)    world position (a container's drop lands within 0.7 of it)
needs        objective indices done before it was taken in the mapping runs
extra        weapon-group tokens it needs beyond those objectives
container    True for a pack dropped by a cabinet, box or safe when opened
"""

PICKUPS = {
    'Time to Split': [
        (0, 'Health', (2,), ('Easy', 'Normal', 'Hard'), (58.26, -8.33, -52.84), (), (), False),
        (1, 'Health', (3,), ('Easy', 'Normal'), (-78.60, -12.40, -95.35), (), (), False),
        (2, 'Health', (1,), ('Easy', 'Normal', 'Hard'), (-92.33, -6.67, -212.61), (), (), False),
        (3, 'Health', (0,), ('Easy', 'Normal', 'Hard'), (-95.37, -6.84, -208.63), (1,), (), False),
        (4, 'Health', (14,), ('Easy', 'Normal', 'Hard'), (-72.21, -7.19, -239.41), (1,), (), False),
        (5, 'Health', (15,), ('Easy', 'Normal', 'Hard'), (-72.77, -7.32, -234.66), (1, 2), (), False),
    ],
    'Scotland the Brave': [
        (0, 'Armour', (45,), ('Easy', 'Normal', 'Hard'), (39.98, -29.23, 34.73), (), (), False),
        (1, 'Armour', (30,), ('Easy', 'Normal', 'Hard'), (21.55, -20.94, 12.38), (), (), False),
        (2, 'Health', (27,), ('Easy',), (21.36, -20.94, -10.46), (), (), False),
        (3, 'Health', (40, 41), ('Easy', 'Normal', 'Hard'), (48.64, -40.37, -41.06), (10,), (), False),
        (4, 'Health', (29,), ('Easy',), (-3.20, -12.92, 53.51), (10,), (), False),
        (5, 'Armour', (32,), ('Easy', 'Normal', 'Hard'), (-32.65, 4.10, -23.86), (1, 10), (), False),
        (6, 'Health', (44,), ('Easy', 'Normal', 'Hard'), (-30.89, -5.89, 33.84), (1, 10), (), False),
        (7, 'Health', (11,), ('Easy', 'Normal', 'Hard'), (-11.54, 0.00, 31.65), (1, 3, 10), (), False),
        (8, 'Armour', (34,), ('Easy', 'Normal', 'Hard'), (4.62, 1.94, -11.70), (1, 3, 7, 10), (), False),
        (9, 'Health', (19,), ('Easy', 'Normal', 'Hard'), (-21.77, -4.12, 24.75), (1, 3, 6, 7, 10), (), False),
    ],
    'The Russian Connection': [
        (0, 'Armour', (3,), ('Easy', 'Normal', 'Hard'), (1.74, -3.16, 25.12), (), (), False),
        (1, 'Health', (8, 9), ('Easy', 'Normal', 'Hard'), (-79.91, 0.84, -42.19), (), (), False),
        (2, 'Armour', (6,), ('Easy', 'Normal', 'Hard'), (-76.29, 7.15, -0.68), (1, 2, 9), (), False),
        (3, 'Health', (15,), ('Easy', 'Normal', 'Hard'), (-156.66, -7.00, 1.31), (1, 2, 9), (), False),
        (4, 'Health', (18, 19), ('Easy', 'Normal', 'Hard'), (-150.41, -5.05, 5.54), (1, 2, 3, 4, 5, 6, 9), (), False),
        (5, 'Armour', (23,), ('Easy', 'Normal', 'Hard'), (-151.49, -5.05, 5.52), (1, 2, 3, 4, 5, 6, 9), (), False),
        (6, 'Health', (22,), ('Easy', 'Normal', 'Hard'), (-175.66, -6.46, 5.78), (1, 2, 3, 4, 5, 6, 9), (), False),
    ],
    'The Khallos Express': [
        (0, 'Health', (3,), ('Easy', 'Normal', 'Hard'), (-111.40, 0.28, 2.35), (), (), False),
        (1, 'Health', (5,), ('Easy', 'Normal', 'Hard'), (-141.75, -1.13, 1.68), (), (), False),
        (2, 'Armour', (2,), ('Easy', 'Normal', 'Hard'), (-155.75, 0.76, 2.92), (), (), False),
        (3, 'Armour', (23,), ('Easy', 'Normal', 'Hard'), (-302.25, 0.42, 0.27), (), (), False),
        (4, 'Health', (22,), ('Easy', 'Normal', 'Hard'), (-302.19, 1.82, -2.26), (), (), False),
        (5, 'Health', (21,), ('Easy', 'Normal', 'Hard'), (-309.78, -0.95, -2.52), (), (), False),
        (6, 'Health', (1,), ('Easy', 'Normal', 'Hard'), (-373.25, 0.42, -0.19), (0,), (), False),
        (7, 'Armour', (0,), ('Easy', 'Normal', 'Hard'), (-499.90, -2.00, 2.76), (0, 1, 2, 3), (), False),
        (0, 'Health', (), ('Easy', 'Normal', 'Hard'), (-422.80, 1.30, -2.40), (0, 1, 2), (), True),
    ],
    'Mansion of Madness': [
        (0, 'Health', (21,), ('Easy', 'Normal', 'Hard'), (-41.60, 18.23, 1.36), (1, 4), ('FIRE',), False),
        (1, 'Health', (20,), ('Easy', 'Normal', 'Hard'), (-5.65, 1.80, 62.16), (1, 4), ('FIRE',), False),
        (2, 'Health', (22,), ('Easy', 'Normal', 'Hard'), (21.57, 1.05, 71.25), (1, 3, 4), ('FIRE',), False),
        (0, 'Health', (), ('Easy', 'Normal', 'Hard'), (-24.28, 0.50, 5.93), (), ('FIRE',), True),
        (1, 'Health', (), ('Easy', 'Normal', 'Hard'), (-26.60, 0.16, 1.95), (), ('FIRE',), True),
        (2, 'Health', (), ('Easy', 'Normal', 'Hard'), (-21.64, 6.16, 65.55), (1,), ('FIRE',), True),
        (3, 'Health', (), ('Easy', 'Normal', 'Hard'), (-16.95, 6.50, 67.84), (1,), ('FIRE',), True),
        (4, 'Health', (), ('Easy', 'Normal', 'Hard'), (-32.24, 12.16, 48.88), (1,), ('FIRE',), True),
    ],
    'What Lies Below': [
        (0, 'Health', (7, 8), ('Easy', 'Normal', 'Hard'), (23.70, -36.00, 72.13), (1,), ('GHOST',), False),
        (1, 'Health', (19,), ('Easy', 'Normal', 'Hard'), (22.88, -36.00, 41.39), (1, 2), ('GHOST',), False),
        (2, 'Health', (11, 12), ('Easy', 'Normal', 'Hard'), (6.26, -73.06, 18.92), (1,), ('GHOST',), False),
    ],
    'Breaking and Entering': [
        (0, 'Health', (2,), ('Easy', 'Normal', 'Hard'), (2.89, 10.00, -6.34), (), (), False),
        (1, 'Armour', (9,), ('Easy', 'Normal', 'Hard'), (7.91, 10.00, -3.30), (), (), False),
        (2, 'Health', (6,), ('Easy', 'Normal', 'Hard'), (2.65, 6.95, 7.83), (1,), (), False),
        (3, 'Armour', (10,), ('Easy', 'Normal', 'Hard'), (2.64, 6.95, 6.81), (1,), (), False),
        (4, 'Health', (7,), ('Easy', 'Normal', 'Hard'), (-10.02, 0.58, 31.48), (1, 2, 3), (), False),
        (5, 'Armour', (11,), ('Easy', 'Normal', 'Hard'), (-3.14, 0.58, 33.18), (1, 2, 3), (), False),
        (6, 'Health', (8,), ('Easy', 'Normal', 'Hard'), (47.43, 1.00, 29.98), (1, 2, 3), (), False),
    ],
    'You Genius, U-Genix': [
        (0, 'Armour', (0, 1), ('Easy', 'Normal', 'Hard'), (-72.19, 8.80, -71.10), (1,), (), False),
        (1, 'Armour', (20, 21), ('Easy', 'Normal', 'Hard'), (-71.51, -0.59, 1.29), (1, 2, 3), (), False),
        (2, 'Health', (18, 19), ('Easy', 'Normal', 'Hard'), (-63.63, -0.59, 7.79), (1, 2, 3), (), False),
        (3, 'Health', (14,), ('Easy', 'Normal', 'Hard'), (-22.90, 6.98, 8.56), (1, 2, 3, 6), (), False),
        (4, 'Armour', (15,), ('Easy', 'Normal', 'Hard'), (-32.56, 6.98, 5.83), (1, 2, 3, 6), (), False),
        (5, 'Health', (11,), ('Easy', 'Normal', 'Hard'), (6.28, 1.05, 82.64), (1, 2, 3, 6, 14, 15, 16, 18, 19), (), False),
        (6, 'Health', (9,), ('Easy', 'Normal', 'Hard'), (-96.92, 6.32, 32.39), (1, 2, 3), (), False),
        (7, 'Health', (3, 4), ('Easy', 'Normal', 'Hard'), (-106.93, 1.05, 3.01), (1, 2), (), False),
        (8, 'Health', (6, 7), ('Easy', 'Normal', 'Hard'), (-138.09, 3.69, 66.24), (1, 2, 3), (), False),
    ],
    'Machine Wars': [
        (0, 'Health', (0, 1), ('Easy', 'Normal', 'Hard'), (80.65, -3.89, -73.60), (), (), False),
        (1, 'Health', (14, 15), ('Easy', 'Normal', 'Hard'), (27.41, 4.12, -244.08), (0,), (), False),
        (2, 'Health', (21,), ('Easy', 'Normal', 'Hard'), (-8.38, 6.25, -179.85), (0, 1, 2), (), False),
        (3, 'Armour', (7,), ('Easy', 'Normal', 'Hard'), (-51.68, 12.64, -177.68), (0, 1, 2), (), False),
        (4, 'Health', (3,), ('Easy',), (-9.16, 2.38, -158.54), (0, 1, 2), (), False),
        (5, 'Health', (4,), ('Easy', 'Normal', 'Hard'), (-23.67, 4.86, -128.04), (0, 1, 2), (), False),
        (6, 'Armour', (6,), ('Easy', 'Normal', 'Hard'), (43.72, 4.49, -132.24), (0, 1, 2), (), False),
        (7, 'Health', (29, 30), ('Easy', 'Normal', 'Hard'), (429.97, -4.45, -486.88), (0, 1, 2), (), False),
        (8, 'Health', (8,), ('Easy', 'Normal', 'Hard'), (260.59, 14.48, -438.73), (0, 1, 2), (), False),
    ],
    'Something to Crow About': [
        (0, 'Armour', (2,), ('Easy', 'Normal', 'Hard'), (-71.71, 45.75, 284.31), (), (), False),
        (1, 'Health', (35,), ('Easy', 'Normal', 'Hard'), (-89.84, 45.75, 279.99), (), ('ELECTRO',), False),
        (2, 'Armour', (4,), ('Easy', 'Normal', 'Hard'), (-42.32, 33.03, 239.10), (), ('ELECTRO',), False),
        (3, 'Health', (1,), ('Easy', 'Normal', 'Hard'), (-42.39, 33.03, 245.43), (), ('ELECTRO',), False),
        (4, 'Health', (14,), ('Easy', 'Normal', 'Hard'), (31.32, 62.94, 248.54), (), ('ELECTRO',), False),
        (5, 'Armour', (15,), ('Easy', 'Normal', 'Hard'), (-19.24, 50.00, 220.22), (), ('ELECTRO',), False),
        (6, 'Health', (36,), ('Easy', 'Normal', 'Hard'), (13.25, 50.00, 218.32), (1, 2), ('ELECTRO',), False),
        (7, 'Health', (3,), ('Easy', 'Normal', 'Hard'), (0.05, 57.25, 282.09), (1, 2), ('ELECTRO',), False),
        (8, 'Armour', (37,), ('Easy', 'Normal', 'Hard'), (42.59, 32.75, 195.63), (), ('ELECTRO',), False),
        (9, 'Health', (17,), ('Easy', 'Normal', 'Hard'), (30.63, 32.75, 143.86), (), ('ELECTRO',), False),
        (10, 'Armour', (18,), ('Easy', 'Normal', 'Hard'), (48.89, 30.38, 120.31), (1, 2), ('ELECTRO',), False),
        (11, 'Health', (20,), ('Easy', 'Normal', 'Hard'), (153.50, 67.47, 117.88), (1, 2), ('ELECTRO',), False),
        (12, 'Health', (6,), ('Easy', 'Normal', 'Hard'), (119.62, 78.50, 87.30), (1, 2, 3), ('ELECTRO',), False),
        (13, 'Armour', (7,), ('Easy', 'Normal', 'Hard'), (268.88, 79.63, 66.46), (1, 2, 3), ('ELECTRO',), False),
        (14, 'Health', (8,), ('Easy', 'Normal', 'Hard'), (268.74, 79.63, 95.23), (1, 2, 3), ('ELECTRO',), False),
    ],
    'You Take the High Road': [
        (0, 'Armour', (5,), ('Easy', 'Normal', 'Hard'), (-35.99, -7.51, 141.37), (), (), False),
        (1, 'Health', (6,), ('Easy', 'Normal', 'Hard'), (-36.22, -7.50, 142.57), (), (), False),
        (2, 'Health', (9, 10), ('Easy', 'Normal', 'Hard'), (-21.30, -15.81, 125.54), (), (), False),
        (3, 'Armour', (14,), ('Easy', 'Normal', 'Hard'), (21.09, -15.71, 108.55), (), (), False),
        (4, 'Health', (18,), ('Easy',), (125.84, -16.60, 69.45), (), (), False),
        (5, 'Health', (17,), ('Easy', 'Normal', 'Hard'), (126.81, -32.45, 103.05), (), (), False),
        (6, 'Armour', (20,), ('Easy', 'Normal', 'Hard'), (126.77, -16.61, 66.17), (), (), False),
    ],
    'The Hooded Man': [
        (0, 'Health', (0,), ('Easy', 'Normal', 'Hard'), (-44.06, -5.67, -105.42), (1,), (), False),
    ],
    'Future Perfect': [
        (0, 'Armour', (6,), ('Easy', 'Normal', 'Hard'), (71.83, -12.04, 5.77), (), (), False),
        (1, 'Health', (4,), ('Easy', 'Normal', 'Hard'), (24.23, -12.04, 2.99), (), (), False),
    ],
}

# spots reachable without their extra tokens but out of logic: (mission, .war indices)
SEQUENCE_BREAK = [('Something to Crow About', (35,))]

# spots never actually taken in a mapping run: (mission, n, container). They stay
# excluded (filler only) until a run takes them.
UNVERIFIED = [('Mansion of Madness', 1, True), ('Something to Crow About', 4, False), ('Something to Crow About', 8, False), ('Something to Crow About', 9, False), ('You Take the High Road', 3, False)]
