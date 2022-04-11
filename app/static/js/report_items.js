function addReportItemGraphToDOM(parameters, reportDOMId="report_items"){

// todo: use DOMsanitize to counter XSS

    const graphId = parameters.id + "_plot";

    // generate html elements of a graph area
    var newReportItemDOM = ml("div", { id: parameters.id, class: "chart", style: "height: fit-content;"}, [
            ml("div", { class: "chart__header"}, [
                ml("div", {}, [
                    ml("span", { class: "title"}, parameters.title)
                ]),
                ml("div", { class: "dropdown"}, [
                    ml("button", { class: "btn dropdown-toggle btn--transparent", type: "button", id: "dropdownMenuTS", 'data-bs-toggle': "dropdown", 'aria-expanded': "false"}, [
                       ml("span", { class: "icon icon-more"}, [])
                    ]),
                    ml("ul", { class: "dropdown-menu", 'aria-labelledby': "dropdownMenuTS"}, [
                        ml("li", { class: "dropdown-item"}, ml("a", {href: urlNotImplemented}, "Export as .xls")),
                        ml("li", { class: "dropdown-item"}, ml("a", {href: urlNotImplemented}, "Export as .pdf")),
                        ml("li", { class: "dropdown-item"}, ml("a", {href: urlCopyReportItem}, "Copy item")),
                        ml("li", { class: "dropdown-item"}, ml("button", {onclick: deleteReportItem, "data-report-item-id": parameters.id }, "Delete item")),
                    ]),
                ]),
            ]),
            ml("div", { class: "chart__plot"}, ml("div", {id: graphId}, [])),
        ]
    );

    // append the graph to the DOM
    document.getElementById(reportDOMId).appendChild(newReportItemDOM);

    return graphId

};



// credits: https://idiallo.com/javascript/create-dom-elements-faster
function ml(tagName, props, nest) {
    var el = document.createElement(tagName);
    if(props) {
        for(var name in props) {
            if(name.indexOf("on") === 0) {
                el.addEventListener(name.substr(2).toLowerCase(), props[name], false)
            } else {
                el.setAttribute(name, props[name]);
            }
        }
    }
    if (!nest) {
        return el;
    }
    return nester(el, nest)
}

// credits: https://idiallo.com/javascript/create-dom-elements-faster
function nester(el, n) {
    if (typeof n === "string") {
        var t = document.createTextNode(n);
        el.appendChild(t);
    } else if (n instanceof Array) {
        for(var i = 0; i < n.length; i++) {
            if (typeof n[i] === "string") {
                var t = document.createTextNode(n[i]);
                el.appendChild(t);
            } else if (n[i] instanceof Node){
                el.appendChild(n[i]);
            }
        }
    } else if (n instanceof Node){
        el.appendChild(n)
    }
    return el;
}


function addTimeseriesGraph(graphId, parameters){
    // prepare traces in ploty format
    var data = []
    parameters.data.forEach(scenario => {
        scenario.timeseries.forEach(timeseries => {
            // todo provide a function to format the name of the timeseries
            data.push({x: scenario.timestamps,
                y: timeseries.value,
                name:scenario.scenario_name + timeseries.label + timeseries.unit,
                type: 'scatter',
                line: {shape: 'hv'},
            })
        });
    });
    // prepare graph layout in plotly format
    const layout= {
        title: parameters.title,
        xaxis:{
            title: parameters.x_label,
        },
        yaxis:{
            title: parameters.y_label,
        },
        showlegend: true
    }
    // create plot
    Plotly.newPlot(graphId, data, layout);
};


function addStackedTimeseriesGraph(graphId, parameters){
    // prepare traces in ploty format
    var data = []
    parameters.data.forEach(scenario => {
        scenario.timeseries.forEach(timeseries => {
            // todo provide a function to format the name of the timeseries
            data.push({x: scenario.timestamps,
                y: timeseries.value,
                name:scenario.scenario_name + timeseries.label + timeseries.unit,
                type: 'scatter',
                line: {shape: 'hv'},
                stackgroup: timeseries.asset_type,
                fill: timeseries.fill
            })
        });
    });
    // prepare graph layout in plotly format
    const layout= {
        title: parameters.title,
        xaxis:{
            title: parameters.x_label,
        },
        yaxis:{
            title: parameters.y_label,
        }
    }
    // create plot
    Plotly.newPlot(graphId, data, layout);
};


function addCapacitiyGraph(graphId, parameters){
    // prepare traces in ploty format
    var data = []
    parameters.data.forEach(scenario => {
        scenario.timeseries.forEach(timeseries => {
            // todo provide a function to format the name of the timeseries

            data.push({
                x: scenario.timestamps,
                y: timeseries.capacity,
                name:timeseries.name,
                type: 'bar',
                // line: {shape: 'hv'},
                // stackgroup: timeseries.asset_type,
                // fill: timeseries.fill
            })
        });
    });

    // prepare graph layout in plotly format
    const layout= {
        title: parameters.title,
        barmode: 'stack',
        showlegend: true
    }
    // create plot
    Plotly.newPlot(graphId, data, layout);
};

function addSankeyDiagram(graphId, parameters){


    console.log(parameters)
    // prepare graph layout in plotly format
    const layout= {
        title: parameters.title,
    }
    // create plot
    Plotly.newPlot(graphId, parameters.data.data, layout);
};


function addSensitivityAnalysisGraph(graphId, parameters){
    // prepare graph layout in plotly format
    const layout= {
        title: parameters.title,
        xaxis:{
            title: parameters.x_label,
        },
        yaxis:{
            title: parameters.y_label,
        }
    }
    // create plot
    console.log(parameters)
    Plotly.newPlot(graphId, parameters.data, layout);
};


// TODO write functions for other report types
const graph_type_mapping={
    timeseries: addTimeseriesGraph,
    timeseries_stacked: addStackedTimeseriesGraph,
    capacities: addCapacitiyGraph,
    sensitivity_analysis: addSensitivityAnalysisGraph,
    sankey: addSankeyDiagram
}
// # GRAPH_TIMESERIES = "timeseries"
// # GRAPH_TIMESERIES_STACKED = "timeseries_stacked"
// # GRAPH_CAPACITIES = "capacities"
// # GRAPH_BAR = "bar"
// # GRAPH_PIE = "pie"
// # GRAPH_LOAD_DURATION = "load_duration"
// # GRAPH_SANKEY = "sankey"


var existingReportItemsData = JSON.parse(document.getElementById('existingReportItemsData').textContent);
existingReportItemsData.forEach(reportItem => {
    var graphId = addReportItemGraphToDOM(reportItem);
    if(reportItem.type in graph_type_mapping){
        graph_type_mapping[reportItem.type](graphId, reportItem);
    }
    else{
        console.log("the report type '" + reportItem.type + "' is not yet supported, sorry");
    }

});
