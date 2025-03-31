import os
import time
import datetime
import random
import json
import paho.mqtt.client as mqtt
import pandas as pd
import csv
import sys

import dash
from dash import Dash, dcc, html, Input, Output, State, callback, ctx
import plotly.express as px
import plotly.graph_objects as go
import plotly

class Data:
    def __init__(self, window_size, logfile, columns, save_measure=False):
        self.save = save_measure
        self.columns = columns 
        self.__csv_columns = self.columns + ["milliseconds"]
        self.df = pd.DataFrame(columns=self.columns)
        self.window_size = window_size
        self.__t0_ms = time.time() * 1000    
    
        self.__logfile = open(logfile, "a")
        self.__csv_writer = csv.DictWriter(self.__logfile, self.__csv_columns)

    @property
    def shape(self):
        return len(self.df.shape)

    def insert(self, data):
        self.df = pd.concat([self.df, pd.DataFrame([data])], ignore_index=True).tail(self.window_size)

    def reset(self):
        self.df.drop(self.df.index, inplace=True) 

    def insert_random(self):
        data = {key: random.uniform(1, 10) for key in self.columns}
        self.insert(data)
        return data

    def __getitem__(self, key):
        if key == "time":
            return list(self.df.index.values)
        return list(self.df[key])
   
    def close_logfile(self):
        self.__logfile.close()

    def save_measurement(self, data):
        if self.save:
            data.update({"milliseconds": (time.time() * 1000) - self.__t0_ms})
            self.__csv_writer.writerow(data)


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected with result code {reason_code}")
    client.subscribe("debug/")

def on_message(client, userdata, msg):
    msg.payload = msg.payload.decode("utf-8")
    msg_dict = json.loads(msg.payload)
    msg_dict.update({"timestamp": datetime.datetime.now().strftime("%H-%M-%S")})
    
    data.insert(msg_dict)
    data.save_measurement(msg_dict)

@callback(Output('depth-graph', 'figure'), 
            Input('interval', 'n_intervals'))
def update_graph_live(n):
    fig = plotly.tools.make_subplots(rows=3, cols=3, vertical_spacing=0.2,
                                subplot_titles=("Z-Axis", "Pitch", "Roll",
                                                "ForceZ", "ForcePitch", "ForceRoll",
                                                "speedZ"))
    # if in test mode use random data
    if test_mode:
        data.insert_random()
    
    # Plot depth, pitch e roll con relativi riferimenti
    fig.append_trace(go.Line(x=data["time"], y=data["depth"], line_color="blue", name="depth"), 1, 1)
    fig.append_trace(go.Line(x=data["time"], y=data["reference_z"], line_color="red", name="refZ"), 1, 1)
    
    fig.append_trace(go.Line(x=data["time"], y=data["pitch"], line_color="blue", name="pitch"), 1, 2)
    fig.append_trace(go.Line(x=data["time"], y=data["reference_pitch"], line_color="red", name="refPitch"), 1, 2)
    
    fig.append_trace(go.Line(x=data["time"], y=data["roll"], line_color="blue", name="roll"), 1, 3)
    fig.append_trace(go.Line(x=data["time"], y=data["reference_roll"], line_color="red", name="refRoll"), 1, 3)

    # Plot delle accelerazioni assiali
    #fig.append_trace(go.Line(x=data["time"], y=data["accX"], line_color="black", name="accX"), 2, 1)
    #fig.append_trace(go.Line(x=data["time"], y=data["accY"], line_color="black", name="accY"), 2, 2)
    #fig.append_trace(go.Line(x=data["time"], y=data["accZ"], line_color="black", name="accZ"), 2, 3)
    
    # Plot della forza in output dal controllore
    fig.append_trace(go.Line(x=data["time"], y=data["force_z"], line_color="green", name="forceZ"), 2, 1)
    fig.append_trace(go.Line(x=data["time"], y=data["force_pitch"], line_color="green", name="forcePitch"), 2, 2)
    fig.append_trace(go.Line(x=data["time"], y=data["force_roll"], line_color="green", name="forceRoll"), 2, 3)

    # Plot vertical speed
    fig.append_trace(go.Line(x=data["time"], y=data["Zspeed"], line_color="black", name="speedZ"), 3, 1)
    

    fig.update_layout(height=800, width=1400, showlegend=False)
    fig.update_layout(showlegend=False)

    return fig

@callback(Input('reset-flag', 'n_clicks'))
def update_output(n_clicks):
    if "reset-flag" == ctx.triggered_id:
        data.reset()

def create_save_dir(csv_columns, dirname="saves"):
    """ Ritorna il path assoluto del file di log """
    
    # Path della cartella di log, verificare se esiste e in caso crearla
    working_dir = os.path.dirname(os.path.abspath(__file__))
    save_dir = os.path.join(working_dir, dirname)

    if not os.path.isdir(save_dir):
        print("Creating Save directory")
        os.mkdir(save_dir)
    else:
        print("Saving directory exists")
    
    # Definizione del filname per il logfile 
    logfile_name = f"{datetime.date.today()}.csv"
    logfile_path = os.path.join(save_dir, logfile_name)

    if not os.path.exists(logfile_path):
        with open(logfile_path, "w") as f:
            csv_writer = csv.DictWriter(f, csv_columns)
            csv_writer.writeheader()

    return logfile_path 

columns = ["Zacc", "Zspeed", "bar_state", "controller_state", "depth", "external_temperature",
           "force_pitch", "force_roll", "force_z", "imu_state", "internal_temperature", "motor_thrust", 
           "motor_thrust_max_xy", "motor_thrust_max_z", "pitch", "pwm", "reference_pitch",
           "reference_roll", "reference_z", "roll", "rov_armed", "yaw"]

if len(sys.argv) > 1: 
    test_mode = bool(sys.argv[1])
else:
    test_mode = False

app = Dash(__name__)
app.layout = html.Div([
    html.Div([
        html.H4("EVA Debug Information")
    ]),
    html.Div([
        #html.Button("SUBMIT WINDOW", id="submit-window-button"),
        #html.Button("CHANGE INTERVAL", id="change-interval-button")
    ]),
    html.Div([
        dcc.Graph(id="depth-graph"),
        dcc.Interval(id="interval", interval=200, n_intervals=0)
    ]),
    html.Div([
        html.Button("RESET", id="reset-flag")
    ])
])

if __name__ == "__main__":
    logfile_path = create_save_dir(columns)
    data = Data(100, logfile_path, columns)
    
    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message
    
    if not test_mode:
        mqttc.connect("10.0.0.254", 1883, 60)
        mqttc.loop_start()
    
    app.run()
    
    mqttc.loop_stop()
    data.close_logfile()
