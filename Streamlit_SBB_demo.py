import numpy as np
import pandas as pd
import seaborn as sns
from h3 import h3
import folium
from geojson import Feature, Point, FeatureCollection
import json
import matplotlib
import plotly.express as px
from shapely.geometry import Polygon
import streamlit as st



#gives the hexagon in which a lat long lies
def geo_to_h3(row):
        return h3.geo_to_h3(lat=row.y,lng=row.x,resolution = H3_res)

        
#some geometry shenanigans
def add_geometry(row):
  points = h3.h3_to_geo_boundary(row['h3_cell'], True)
  
  return Polygon(points)

def hexagons_dataframe_to_geojson(df_hex, hex_id_field,geometry_field, value_field, name_field,file_output = None):

    list_features = []

    for i, row in df_hex.iterrows():
        feature = Feature(geometry = row[geometry_field],
                          id = row[hex_id_field],
                          properties = {"value": row[value_field]},
                          name = row[name_field])
        list_features.append(feature)

    feat_collection = FeatureCollection(list_features)

    if file_output is not None:
        with open(file_output, "w") as f:
            json.dump(feat_collection, f)

    else :
      return feat_collection


def get_color(custom_cm, val, vmin, vmax):
    return matplotlib.colors.to_hex(custom_cm((val-vmin)/(vmax-vmin)))
#not too sure this is really used given that i go w plotly but ill keep for now
def choropleth_map(df_aggreg, column_name = "value", border_color = 'white', fill_opacity = 0.7, color_map_name = "Blues", initial_map = None):
    
    """
    Creates choropleth maps given the aggregated data. initial_map can be an existing map to draw on top of.
    """    
    #colormap
    min_value = df_aggreg[column_name].min()
    max_value = df_aggreg[column_name].max()
    mean_value = df_aggreg[column_name].mean()
    print(f"Colour column min value {min_value}, max value {max_value}, mean value {mean_value}")
    print(f"Hexagon cell count: {df_aggreg['hex_id'].nunique()}")
    
    # the name of the layer just needs to be unique, put something silly there for now:
    name_layer = "Choropleth " + str(df_aggreg)
    
    if initial_map is None:
        initial_map = folium.Map(location= [47, 4], zoom_start=5.5, tiles="cartodbpositron")

    #create geojson data from dataframe
    geojson_data = hexagons_dataframe_to_geojson(df_hex = df_aggreg, column_name = column_name)

    # color_map_name 'Blues' for now, many more at https://matplotlib.org/stable/tutorials/colors/colormaps.html to choose from!
    custom_cm = matplotlib.cm.get_cmap(color_map_name)

    folium.GeoJson(
        geojson_data,
        style_function=lambda feature: {
            'fillColor': get_color(custom_cm, feature['properties'][column_name], vmin=min_value, vmax=max_value),
            'color': border_color,
            'weight': 1,
            'fillOpacity': fill_opacity 
        }, 
        name = name_layer
    ).add_to(initial_map)

    return initial_map


st.title("Mini-Pototyp")

tab_setup, tab_bhf, tab_bil, tab_scatter = st.tabs([ "Setup","Bahnhöfe", "Vergleich mit Park'n'ride", "Scatterplot"])


#set zoom
with tab_setup:
    st.header("Setup")
    st.write("Der Setup tab dient dazu den Path der Daten und die Grösse der Hexagone zu bestimmen")
    path_base = st.text_input('Path der Daten', f"/Users/labor/Desktop/Private/")
    H3_res = st.radio("Grösse der Hexagone", [6,7,8])
    
with tab_bhf:
    st.header("Bahnhöfe")
    with st.expander("Mehr erfahren"): 
        st.write("In diesem Tab wurden die Bahnhöfe gemäss SBB öffentlichen Daten geladen. Danach wurden die geodaten tesseliert und in einer Karte, gemäss Ihrer Nutzung angezeigt.")
        st.caption(r"https://data.sbb.ch/pages/home20/")
    #load data of stations
    path = path_base+"passagierfrequenz.csv"

    Data_pre = pd.read_csv(path, delimiter= ";")
    Data_pre = Data_pre.drop(columns= [ "Bezugsjahr", "Eigner", "DWV", "DNWV", "Bemerkung", "Bemerkungen","Bemerkungen.1", "Note", "lod"])
    Geopos = Data_pre["Geoposition"].str.split(pat ="," ,expand=True)#
    Geopos = Geopos.rename(columns = {0: "y", 1: "x"})
    Data = pd.concat([Data_pre, Geopos], axis=1).drop(columns = ["Geoposition"])
    Data.x = Data.x.astype(float)
    Data.y = Data.y.astype(float)
    Data["DTV_log"] = np.log(Data.DTV)
    #add h3 hex info
    Data['h3_cell'] = Data.apply(geo_to_h3,axis=1)
    Data = Data.drop(index = Data[Data["h3_cell"]== "0"].index)
    Data['geometry'] = Data.apply(add_geometry,axis=1)
    #make hexagons to shapes that can be displayed
    geojson_obj_bhf = (hexagons_dataframe_to_geojson
                    (Data,
                    hex_id_field='h3_cell',
                    value_field='DTV_log',
                    geometry_field='geometry',
                    name_field= "Bahnhof_Haltestelle"))
    #makes the figure 
    fig = (px.choropleth_mapbox(
                        Data, 
                        geojson=geojson_obj_bhf, 
                        locations='h3_cell', 
                        color=Data["DTV_log"],
                        hover_name = Data["Bahnhof_Haltestelle"],
                        color_continuous_scale="turbo",
                        range_color=(0,Data["DTV_log"].max()),                 
                        mapbox_style='carto-positron',
                        zoom=9,
                        center = {"lat": 47.41609409868053, "lon": 8.553879741076177},
                        opacity=0.7,
                        labels={'count':'# of fire ignitions '}))
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container = True)


#get data from the parkandride
with tab_bil:
    path = path_base+"mobilitat.csv"

    Data_serv = pd.read_csv(path, delimiter= ";")

    Data_serv = Data_serv[Data_serv.parkrail_anzahl.notna()]
    Data_serv_useful = Data_serv[["parkrail_anzahl", "Abkuerzung Bahnhof", "Geoposition" ]]
    Geopos_2 = Data_serv_useful["Geoposition"].str.split(pat ="," ,expand=True)#
    Geopos_2 = Geopos_2.rename(columns = {0: "y", 1: "x"})
    Data_serv_useful = pd.concat([Data_serv_useful, Geopos_2], axis=1).drop(columns = ["Geoposition"])
    Data_serv_useful.x = Data_serv_useful.x.astype(float)
    Data_serv_useful.y = Data_serv_useful.y.astype(float)
    Data_serv_useful['h3_cell'] = Data_serv_useful.apply(geo_to_h3,axis=1)
    Data_serv_useful = Data_serv_useful.drop(index = Data_serv_useful[Data_serv_useful["h3_cell"]== "0"].index)

    #load hexagons into dicts, get thier neibours and update the usage data into a dataframe

    radius =  st.radio ( "radius of influence in Hexagons", [5,6, 7])

    Data_g = Data[["h3_cell", "DTV_log"]].groupby(by = "h3_cell").mean()
    stationdict = Data_g.to_dict()
    stationdict = stationdict["DTV_log"]
    stationinfluence = {}
    for center_hex in stationdict:
        for i in range(0,radius):
            ring = h3.hex_ring(center_hex, i)
            for ring_hex in ring:
                stationinfluence[ring_hex] = 0
        #stationinfluence[center_hex] = stationdict[center_hex]
    for center_hex in stationdict:
        for i in range(0,radius):
            ring = h3.hex_ring(center_hex, i)
            for ring_hex in ring:
                stationinfluence[ring_hex] += np.sqrt(stationdict[center_hex ])/((i+1))**2

    Data_pg = Data_serv_useful[["h3_cell", "parkrail_anzahl"]].groupby(by= "h3_cell").sum()
    parkdict = Data_pg.to_dict()
    parkdict = parkdict["parkrail_anzahl"]
    parkinfluence = {}
    for center_hex in parkdict:
        for i in range(0,radius):
            ring = h3.hex_ring(center_hex, i)
            for ring_hex in ring:
                parkinfluence[ring_hex] = 0
        #parkinfluence[center_hex]= parkdict[center_hex]
    for center_hex in parkdict:
        for i in range(0,radius):
            ring = h3.hex_ring(center_hex, i)
            for ring_hex in ring:
                parkinfluence[ring_hex] += np.sqrt(parkdict[center_hex ])/((i+1))**2

    #normalize the dataframes for the looks to be good, add Bilanz
    station_df = pd.DataFrame.from_dict(stationinfluence, orient="index")
    parking_df = pd.DataFrame.from_dict(parkinfluence, orient= "index")
    Totaldf = station_df.join(parking_df, how = "outer" , lsuffix = "station_usage", rsuffix = "parking_usage").rename(columns = {"0station_usage": "station_usage", "0parking_usage": "parking_usage"}).fillna(0)
    Totaldf_norm = (Totaldf / Totaldf.mean()) -Totaldf.std()
    Totaldf_norm["Bilanz"] = Totaldf_norm["station_usage"]-Totaldf_norm["parking_usage"]
    Totaldf_norm = Totaldf_norm.reset_index(level= 0).rename(columns={"index": "h3_cell"})
    
    #same shenanigans as before to show map
    
    Totaldf_norm['geometry'] = Totaldf_norm.apply(add_geometry,axis=1)
    geojson_obj_bil = (hexagons_dataframe_to_geojson
                    (Totaldf_norm,
                    hex_id_field='h3_cell',
                    value_field='Bilanz',
                    geometry_field='geometry',
                    name_field= "h3_cell"))

    fig_2 = (px.choropleth_mapbox(
                        Totaldf_norm, 
                        geojson=geojson_obj_bil, 
                        locations='h3_cell', 
                        color=Totaldf_norm["Bilanz"],
                        hover_name = Totaldf_norm["Bilanz"],
                        color_continuous_scale="turbo",
                        range_color=(-6,Totaldf_norm["Bilanz"].max()),                 
                        mapbox_style='carto-positron',
                        zoom=9,
                        center = {"lat": 47.41609409868053, "lon": 8.553879741076177},
                        opacity=0.6,
                        labels={"Public Park'n'ride compared to daily station usage"}))
    fig_2.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    fig.update_layout(
        title_text="Public Park'n'ride compared to daily station usage")
    st.plotly_chart(fig_2)

#make a new DF and some shit for a scatterplot
with tab_scatter:
    Data_station_scatter = Data[["code", "Kanton", "DTV"]]
    Data_parking_scatter = Data_serv_useful[["parkrail_anzahl"	,"Abkuerzung Bahnhof"]].rename(columns={"Abkuerzung Bahnhof": "code"})

    Data_scatterplot = Data_station_scatter.merge(Data_parking_scatter, how = "outer", on = "code", ).fillna(0)
    fig_3 = px.scatter(Data_scatterplot, x = "DTV", y = "parkrail_anzahl", hover_data=["code"] , color="Kanton" , log_x = True, 
                    
                    )
    fig.update_layout(
        title_text="Scatter plot between usage of the station and park'n'ride availability.")
    st.plotly_chart(fig_3)