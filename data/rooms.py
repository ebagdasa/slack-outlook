from secret import rooms

def get_room_by_no(no):

    for room in rooms:
        if ('Bloomberg %03d' % int(no)) in room['name']:
            return room

    return None


def get_rooms_by_floor(floor):
    room_list = list()
    if int(floor) in [0,1,2,3,4]:
        for room in rooms:
            if 'Bloomberg {0}'.format(floor) in room['name']:
                room_list.append(room)

    return room_list
