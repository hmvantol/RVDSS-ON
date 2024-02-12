import requests
from dash import Dash, dcc, html, Input, Output
import dash_daq as daq
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from bs4 import BeautifulSoup
from functools import reduce
import itertools
from collections import OrderedDict

URL = "https://www.canada.ca/en/public-health/services/surveillance/respiratory-virus-detections-canada.html"

r = requests.get(URL)
soup = BeautifulSoup(r.content, "html5lib")

res = soup.find(
    "span",
    attrs={"class": "badge"},
)
DATA_URL = "https://www.canada.ca" + res.find_previous("a").get("href")

html_tables = pd.read_html(
    requests.get(DATA_URL, timeout=10).content, flavor="bs4", parse_dates=True
)

data = html_tables[4:]

region_menu = OrderedDict(
    [
        ("Can", "All Canada"),
        ("Atl", "Atlantic"),
        ("QC", "Quebec"),
        ("ON", "Ontario"),
        ("Pr", "Prairies"),
        ("BC", "British Columbia"),
        ("Terr", "Territories"),
    ]
)

virus_dict = OrderedDict(
    [
        ("SARS-CoV-2", "Severe acute respiratory syndrome coronavirus 2 (SARS-CoV-2)"),
        ("A", "Influenza A"),
        ("B", "Influenza B"),
        ("RSV", "Respiratory Syncytial Virus (RSV)"),
        ("HPIV", "Human Parainfluenza Virus (HPIV)"),
        ("ADV", "Adenovirus (ADV)"),
        ("HMPV", "Human Metapneumovirus (HMPV)"),
        ("EV/RV", "Enterovirus/Rhinovirus (EV/RV)"),
        ("HCoV", "Human Coronavirus (HCoV)"),
    ]
)

percent_positive = []
cases_detected = []
for i in range(len(data)):
    data[i] = data[i].rename(columns={"Week End": "Week end"})
    percent_positive.append(data[i].loc[:, data[i].columns.str.contains("%")])
    cases_detected.append(data[i].loc[:, data[i].columns.str.contains("Tests")])

for i in range(len(percent_positive)):
    if i == 1:
        double_menu = list(
            itertools.chain.from_iterable(
                itertools.repeat(x, 2) for x in region_menu.keys()
            )
        )
        AB_menu = ["A", "B"] * len(region_menu.keys())
        percent_positive[i].columns = [
            x + " " + y for x, y in zip(double_menu, AB_menu)
        ]
    elif i in [0, 2]:
        percent_positive[i].columns = [
            x + " " + percent_positive[i].columns[0].split(".")[0].rstrip("%")
            for x in region_menu.keys()
        ]
    else:
        percent_positive[i].columns = [
            x + " " + percent_positive[i].columns[0].split(".")[0].rstrip("%")
            for x in list(region_menu.keys())[:-1]
        ]
    percent_positive[i] = pd.concat(
        [data[i].loc[:, "Week end"], percent_positive[i]], axis=1
    )

for i in range(len(cases_detected)):
    cases_detected[i].columns = (
        cases_detected[i].columns.str.rstrip("Tests")
        + [x for x in virus_dict.keys() if x != "B"][i]
    )
    cases_detected[i] = pd.concat(
        [data[i].loc[:, "Week end"], cases_detected[i]], axis=1
    )

cases_detected.append(cases_detected[1].copy())
cases_detected[-1].columns = cases_detected[-1].columns.str.replace("A", "B")
cases_detected[-1].columns = cases_detected[-1].columns.str.replace("Btl", "Atl")
merged1 = reduce(
    lambda left, right: pd.merge(left, right, on="Week end"),
    percent_positive,
)
merged2 = reduce(
    lambda left, right: pd.merge(left, right, on="Week end"),
    cases_detected,
)

long1 = pd.melt(
    merged1,
    id_vars=["Week end"],
    var_name="variable",
    value_name="% positive",
)
col_split = long1.variable.str.split(" ", expand=True)
long1["Region"] = col_split[0]
long1["Virus"] = col_split[1]

long2 = pd.melt(
    merged2,
    id_vars=["Week end"],
    var_name="variable",
    value_name="Cases detected",
)
col_split = long2.variable.str.split(" ", expand=True)
long2["Region"] = col_split[0]
long2["Virus"] = col_split[1]

long1.drop(columns=["variable"], inplace=True)
long2.drop(columns=["variable"], inplace=True)
df = pd.merge(long1, long2, on=["Week end", "Region", "Virus"], how="outer")
df["Virus"] = df["Virus"].replace(virus_dict)

# Sort data by week end, then region, then virus
df = df.sort_values(by=["Week end", "Region", "Virus"])

app = Dash(
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
app.layout = html.Div(
    [
        dcc.Markdown(
            """
# Weekly Respiratory Virus Report

Data comes from the Respiratory Virus Detection Surveillance System ([RVDSS]({url})) of the Public Health Agency of Canada (PHAC).
""".format(
                url=URL
            )
        ),
        html.Div(
            [
                dcc.Dropdown(
                    id="dropdown",
                    options=list(region_menu.values()),
                    value="All Canada",
                    style={"display": "inline-block", "width": "25vw"},
                ),
                html.Div(" ", style={"display": "inline-block", "width": "5vw"}),
                html.Div(
                    "stack", style={"textAlign": "right", "display": "inline-block"}
                ),
                daq.BooleanSwitch(id="switch-unstack", on=False),
                html.Div(
                    "unstack", style={"textAlign": "left", "display": "inline-block"}
                ),
            ],
            style={"display": "flex", "justify-content": "left"},
        ),
        dcc.Graph(id="switch-result", style={"width": "80vw", "height": "110vh"}),
    ]
)


@app.callback(
    Output("switch-result", "figure"),
    Input("switch-unstack", "on"),
    Input("dropdown", "value"),
)
def update_chart(on, region):
    new_region_dict = {v: k for k, v in region_menu.items()}
    new_region_dict[None] = "Can"
    mask = df["Region"] == new_region_dict[region]
    if on:
        fig = px.line(
            df[mask],
            x="Week end",
            y="% positive",
            color="Virus",
            hover_data="Cases detected",
            color_discrete_sequence=px.colors.qualitative.Alphabet,
            facet_row="Virus",
        )
        fig.update_layout(template="plotly_white")
        fig.for_each_yaxis(lambda y: y.update(title="", matches=None))
        fig.for_each_annotation(
            lambda a: a.update(
                text=a.text.split("=")[1],
                textangle=0,
                xanchor="right",
                xref="paper",
                yanchor="bottom",
                yref="paper",
            )
        )
        fig.add_annotation(
            showarrow=False,
            xanchor="center",
            xref="paper",
            x=-0.075,
            yanchor="middle",
            yref="paper",
            y=0.5,
            textangle=270,
            text="% positive (per week)",
        )
    else:
        fig = px.area(
            df[mask],
            x="Week end",
            y="% positive",
            color="Virus",
            hover_data="Cases detected",
            color_discrete_sequence=px.colors.qualitative.Alphabet,
            facet_row=None,
        )
        fig.update_layout(
            yaxis_title="% positive (per week)",
            template="plotly_white",
        )
    return fig


server = app.server

if __name__ == "__main__":
    app.run_server(debug=True, host="0.0.0.0", port=9000)
