from geopy.geocoders import Nominatim
from openlocationcode.openlocationcode import encode

geolocator = Nominatim(user_agent="medren")

# lat, lng = 52.509669, 13.376294
lat, lng = 37.4223041570954, -122.08410042965134

def test_geocode():
    #location = geolocator.geocode("175 5th Avenue NYC")
    location = geolocator.geocode("Zikhron Yaakov, Israel")
    print(location.address)
    # Flatiron Building, 175, 5th Avenue, Flatiron, New York, NYC, New York, ...
    print((location.latitude, location.longitude))
    # (40.7410861, -73.9896297241625)
    print(location.raw)
    # {'place_id': '9167009604', 'type': 'attraction', ...}

def test_reverse():
    location = geolocator.reverse(f"{lat}, {lng}") # lat, lon
    print(location.address)
    #Potsdamer Platz, Mitte, Berlin, 10117, Deutschland, European Union
    print((location.latitude, location.longitude))
    #(52.5094982, 13.3765983)
    print(location.raw)
    #{'place_id': '654513', 'osm_type': 'node', ...}

def test_pluscode():
    pluscode = encode(lat, lng)
    print(pluscode)

if __name__ == '__main__':
    # test_geocode()
    # test_reverse()
    test_pluscode()