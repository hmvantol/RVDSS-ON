import requests
from dash import Dash, dcc, html, Input, Output
import dash_daq as daq
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from bs4 import BeautifulSoup
from functools import reduce


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

covid = data[0][["Week end", "ON Tests", "SARS-CoV-2%.3"]]
flu = data[1][["Week end", "ON Tests", "ON A%", "ON B%"]]
rsv = data[2][["Week end", "ON Tests", "RSV%.3"]]
hpiv = data[3][["Week End", "ON Tests", "HPIV%.3"]]
adv = data[4][["Week End", "ON Tests", "ADV%.3"]]
hmpv = data[5][["Week End", "ON Tests", "HMPV%.3"]]
evrv = data[6][["Week End", "ON Tests", "EV/RV%.3"]]
hcov = data[7][["Week End", "ON Tests", "HCoV%.3"]]
dataframes = [covid, flu, rsv, hpiv, adv, hmpv, evrv, hcov]

for i in range(len(dataframes)):
    dataframes[i] = dataframes[i].rename(columns=lambda x: x.rstrip(".3"))
    dataframes[i] = dataframes[i].rename(
        columns=lambda x: x.replace(
            "ON Tests", dataframes[i].columns[2].rstrip("%") + " detected"
        )
    )
    if "Week End" in dataframes[i].columns:
        dataframes[i] = dataframes[i].rename(columns={"Week End": "Week end"})
    if "ON A detected" in dataframes[i].columns:
        dataframes[i] = dataframes[i].rename(columns={"ON A detected": "Flu detected"})

merged = reduce(
    lambda left, right: pd.merge(left, right, on="Week end"),
    dataframes,
)

long = pd.melt(merged, id_vars=["Week end"], value_vars=merged.columns[1:])
col1 = long.loc[long["variable"].str.endswith("%")]
col1.loc[:, "variable"] = col1["variable"].str.rstrip("%")
col1.columns = ["Week end", "Virus", "% positive"]
col2 = long.loc[long["variable"].str.endswith("detected")]
col2.loc[:, "variable"] = col2["variable"].str.rstrip(" detected")
col2.columns = ["Week end", "Virus", "Cases detected"]
df = pd.merge(col1, col2, on=["Week end", "Virus"], how="outer")
total_flu = df.loc[df["Virus"] == "Flu", "Cases detected"].values
percent_A = df.loc[df["Virus"] == "ON A", "% positive"].values
percent_B = df.loc[df["Virus"] == "ON B", "% positive"].values
A_cases = (total_flu * percent_A / (percent_A + percent_B)).round(0)
B_cases = (total_flu * percent_B / (percent_A + percent_B)).round(0)
df.loc[df["Virus"] == "ON A", "Cases detected"] = A_cases
df.loc[df["Virus"] == "ON B", "Cases detected"] = B_cases
df["Virus"] = df["Virus"].replace(
    {
        "ADV": "Adenovirus (ADV)",
        "EV/RV": "Enterovirus/Rhinovirus (EV/RV)",
        "HCoV": "Human Coronavirus (HCoV)",
        "HMPV": "Human Metapneumovirus (HMPV)",
        "HPIV": "Human Parainfluenza Virus (HPIV)",
        "RSV": "Respiratory Syncytial Virus (RSV)",
        "SARS-CoV-2": "Severe acute respiratory syndrome coronavirus 2 (SARS-CoV-2)",
        "ON A": "Influenza A",
        "ON B": "Influenza B",
    }
)
df = df.dropna()

app = Dash(
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
app.layout = html.Div(
    [
        dcc.Markdown(
            """
# Weekly Ontario Respiratory Virus Report

Data comes from the Respiratory Virus Detection Surveillance System ([RVDSS]({url})) of the Public Health Agency of Canada (PHAC).
""".format(
                url=URL
            )
        ),
        html.Div(
            [
                html.Div(
                    "stack", style={"textAlign": "right", "display": "inline-block"}
                ),
                daq.BooleanSwitch(id="switch-unstack", on=False),
                html.Div(
                    "unstack", style={"textAlign": "left", "display": "inline-block"}
                ),
            ],
            style={"display": "flex", "justify-content": "center"},
        ),
        dcc.Graph(id="switch-result", style={"width": "80vw", "height": "110vh"}),
    ]
)


@app.callback(
    Output("switch-result", "figure"),
    Input("switch-unstack", "on"),
)
def update_output(on):
    if on:
        fig = px.line(
            df,
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
                yanchor="top",
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
            df,
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
