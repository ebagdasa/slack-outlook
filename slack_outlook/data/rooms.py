from secret import rooms
import pytz
from datetime import datetime
import dateutil.parser
eastern = pytz.timezone('US/Eastern')


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


def room_by_email(room_email):
    for room in rooms:
        if room["address"] == room_email:
            return ' '.join(room['name'].split()[3:])

    return 'No room found for {0}.'.format(room_email)


def parse_time_room(iso_datetime):
    date_normal, iso_time = iso_datetime.split('T')
    hour, minute, _ = iso_time.split(':')
    return '{0} {1}:{2}'.format(date_normal, hour, minute)


def get_meeting_info(meeting):
    id = meeting['id']
    start =  parse_time_room(meeting["start"]['dateTime'])
    end = parse_time_room(meeting["end"]['dateTime'])
    location = meeting['location']['displayName']
    timeZone = meeting['end']['timeZone']
    return {'id': id, 'start': start, 'end': end, 'location':location, 'timeZone': timeZone}


def where_room():
    return
