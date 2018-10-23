
def check_floor_json(rooms, time_start, time_end):
    mjson = {
        "isOrganizerOptional": "True",
        "attendees":

            [{
                "type": "required",
                "emailAddress": x
            } for x in rooms]
            ,
        "timeConstraint": {
            "activityDomain": "unrestricted",
            "timeslots": [
                {
                    "start": {
                        "dateTime": time_start,
                        "timeZone": "Eastern Standard Time"
                    },
                    "end": {
                        "dateTime": time_end,
                        "timeZone": "Eastern Standard Time"
                    }
                }
            ]
        },
        "meetingDuration": "PT1H",
        "returnSuggestionReasons": "true",
        "minimumAttendeePercentage": "1"
    }

    return mjson


def find_room_json(room, time_start, time_end):
    mjson = {
              "isOrganizerOptional": "True",
              "attendees":
                  [
                    {
                        "type": "required",
                        "emailAddress": room
                    }
                  ],
              "timeConstraint": {
                "activityDomain": "unrestricted",
                "timeslots": [
                  {
                    "start": {
                      "dateTime": time_start,
                      "timeZone": "Eastern Standard Time"
                    },
                    "end": {
                      "dateTime": time_end,
                      "timeZone": "Eastern Standard Time"
                    }
                  }
                ]
              },
              "meetingDuration": "PT1H",
              "returnSuggestionReasons": "true",
              "minimumAttendeePercentage": "100"
            }

    return mjson


def create_booking_json(user, room, time_start, time_end):
    mjson = {
      "subject": 'Meeting for {0}.'.format(user),
      "body": {
        "contentType": "HTML",
        "content": "This event is created by RoomParking Slackbot, contact Eugene (eugene@cs.cornell.edu) for help."
      },
      "start": {
        "dateTime": time_start,
        "timeZone": "Eastern Standard Time"
      },
      "end": {
        "dateTime": time_end,
        "timeZone": "Eastern Standard Time"
      },
      "location": {
        "displayName": room['name']
      },
      "attendees": [
        {
          "emailAddress": room,
          "type": "resource"
        }
      ]
    }

    return mjson
