import os
import sys
import optparse
import random
from algorithm.reroute import rerouter, estimateRange
from algorithm.Graph import Graph
import time
import statistics

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

import traci
import sumolib

# EVGrid route
# 'gneE53' -> '-gneE64'

# Manchester route
# '122066614#0' -> '167121171#7'

def run(netFile, additionalFile, options=None):
    """execute the TraCI control loop"""
    step = 0
    graph = Graph(netFile, additionalFile)
    mWhList = []

    # EV outputs
    params = {}
    outputs = {}

    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()

        # Add random EV routes
        if step >= 0 and step <= 100 \
           and step % 10 == 0:
            fromEdge = getEVEdges(graph, "")
            toEdge = getEVEdges(graph, fromEdge)

            add_ev(graph, fromEdge, toEdge, str(step), options)

        if step == 150:
            params, algRuntime, csStops = add_ev(graph, 'gneE53', '-gneE64', 'Main', options)
            outputs["algRuntime"] = algRuntime
            outputs["params"] = params
            outputs["csStops"] = csStops

        # Gets output params for EV_Main
        if step >= 151:
            try:
                outputs["evBatteryCapacity"] = float(traci.vehicle.getParameter('EV_Main', 'device.battery.actualBatteryCapacity'))
                outputs["evDistance"] = float(traci.vehicle.getDistance('EV_Main'))
                outputs["evDuration"] = float(traci.vehicle.getLastActionTime('EV_Main'))
                outputs["evDuration"] -= 150
            except:
                print("EV_Main not found")

        step += 1

    print('EV Capacity at end: ', outputs["evBatteryCapacity"])
    print('EV Distance: ', outputs["evDistance"])
    print('EV Routing Duration: ', outputs["evDuration"])

    outputVehicleEndInfo(outputs)

    traci.close()
    sys.stdout.flush()

# Adds electric vehicle wish to route
def add_ev(graph, fromEdge, toEdge, evName, options):
    vehicleID = 'EV_' + evName
    params = buildHyperParams()
    batteryCapacity = params["batteryCapacity"]
    algRuntime = ""
    csStops = []

    # Generate vehicle
    traci.route.add('placeholder_trip_' + evName, [toEdge])
    traci.vehicle.add(vehicleID, 'placeholder_trip_' + evName, typeID='electricvehicle')
    traci.vehicle.setParameter(vehicleID, 'device.battery.actualBatteryCapacity', batteryCapacity)

    # Generates optimal route for EV
    if not options.noalg:
        start_time = time.time()
        route, csStops = rerouter(fromEdge, toEdge, vehicleID, graph, params)
        algRuntime = str(time.time() - start_time)
        print("Reroute algorithm runtime ", vehicleID, ": ", algRuntime)

        if len(route) > 0:
            traci.vehicle.setRoute(vehicleID, route)

            for chargingStation in csStops:
                traci.vehicle.setChargingStationStop(vehicleID, chargingStation.id, duration=chargingStation.Duration)

    return params, algRuntime, csStops

# Adds vehicle type electric vehicle
def add_ev_vtype():
    original_stdout = sys.stdout

    f = open("data/electricvehicles.rou.xml", "r+")
    f.truncate(0)       # Clear file

    with open("data/electricvehicles.rou.xml", "w") as routes:
        sys.stdout = routes
        print("<routes>")
        print("""  <vType id="electricvehicle" accel="0.8" decel="4.5" sigma="0.5" emissionClass="Energy/unknown" minGap="2.5" maxSpeed="40" guiShape="evehicle" vClass="evehicle">
                     <param key="has.battery.device" value="true"/>
                     <param key="maximumBatteryCapacity" value="10000"/>
                     <param key="maximumPower" value="1000"/>
                     <param key="vehicleMass" value="1000"/>
                     <param key="frontSurfaceArea" value="5"/>
                     <param key="airDragCoefficient" value="0.6"/>
                     <param key="internalMomentOfInertia" value="0.01"/>
                     <param key="radialDragCoefficient" value="0.5"/>
                     <param key="rollDragCoefficient" value="0.01"/>
                     <param key="constantPowerIntake" value="100"/>
                     <param key="propulsionEfficiency" value="0.9"/>
                     <param key="recuperationEfficiency" value="0.9"/>
                     <param key="stoppingTreshold" value="0.1"/>
                     <param key="has.tripinfo.device" value="true"/>
                   </vType>""")
        print("</routes>")
        sys.stdout = original_stdout

def buildHyperParams():
    hyperParams = {}

    hyperParams["DistanceFromStart"] = 0.32
    hyperParams["DistanceFromDivider"] = 0.32
    hyperParams["Price"] = 0.12
    hyperParams["VehiclesCharging"] = 0.12
    hyperParams["ChargePerStep"] = 0.12

    hyperParams["MinimumSoC"] = 10
    hyperParams["batteryCapacity"] = 500

    return hyperParams

# Get run parameters
def get_options():
    optParser = optparse.OptionParser()
    optParser.add_option("--nogui", action="store_true",
                         default=False, help="Run the commandline version of sumo")
    optParser.add_option("--noalg", action="store_true",
                         default=False, help="Do not run algorithm on simulation")
    options, args = optParser.parse_args()
    return options

# Utility function to get random edges on network that allows EV vehicles
def getEVEdges(graph, otherEdge):
    while True:
        edge = random.choice(graph.Edges).getID()

        if graph.Net.getEdge(edge).allows('evehicle') and otherEdge != edge:
            break

    return edge

def outputVehicleEndInfo(outputs):
    duration = [cs.Duration for cs in outputs["csStops"]]

    csvRow = str(outputs["params"]).replace(",", "") + "," + str(outputs["evDistance"]) + ',' + \
             str(outputs["evDuration"]) + ',' + str(len(outputs["csStops"])) + ','+ \
             str(duration) + ','+ str(outputs["algRuntime"]) + ','+ \
             str(outputs["evBatteryCapacity"])

    with open('data/EV_Outputs.csv', 'a+') as csv:
        csv.write(csvRow + '\n')
