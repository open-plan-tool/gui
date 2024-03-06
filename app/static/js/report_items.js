// TODO enable translation support

var timeseriesFlowTitle = "Energy flow";
var timeseriesTimeTitle = "Time";
var timeseriesCapacityTitle = "Capacity";
var timeseriesChargeDischargeTitle = "Charge/discharge";
var colorway = ["008753", "F2CD5D", "B2916C", "778EB5", "824670", "991818", "E86C1A"]




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
                        ml("li", {}, ml("a", { class: "dropdown-item", href: urlNotImplemented}, "Export as .xls")),
                        ml("li", {}, ml("a", { class: "dropdown-item", href: urlNotImplemented}, "Export as .pdf")),
                        ml("li", {}, ml("a", { class: "dropdown-item", href: urlCopyReportItem}, "Copy item")),
                        ml("li", {}, ml("button", { class: "dropdown-item", onclick: deleteReportItem, "data-report-item-id": parameters.id }, "Delete item")),
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

var deleteReportItem = (event) => {
    //submit the form to delete a report item
    const reportItemId = event.target.getAttribute("data-report-item-id");
    if(confirm("Are you sure ? This action cannot be undone")){
        $.ajax({
            headers: {'X-CSRFToken': `{{ csrf_token }}` },
            type: "POST",
            url: urlDeleteReportItem,
            data: {report_item_id: reportItemId},
            success: function (jsonRes) {
                document.getElementById(reportItemId).remove();
            },
            error: function (err) {
                console.log(err);
            },
        })
    }
};


var createReportItem = (event) => {
    //submit the form to create a new report item

    // get the data of the form (view report_create_item in )
    const createReportUrl = createReportItemForm.getAttribute("ajax-post-url");

    const formData = new FormData(createReportItemForm);
    $.ajax({
        headers: {'X-CSRFToken': `{{ csrf_token }}` },
        type: "POST",
        url: createReportUrl,
        data: formData,
        processData: false,  // tells jQuery not to treat the data
        contentType: false,   // tells jQuery not to define contentType
        success: function (jsonRes) { // verknüpft mit ReportItem.render_json (Klasse in Models)
            console.log(jsonRes)
            // TODO recieve the graph data and call the function to plot it

            reportItemTitle = '';
            reportItemScenarios = [];
            createReportItemModal.hide();
            // TODO check jsonRes.report_type if it is in a mapping which has the different graph names as key and the corresponding function as values
            // as we want to leave the door open to add other reportItem objects such as table, text, etc...
            const graphId = addReportItemGraphToDOM(jsonRes);
            if(jsonRes.type in graph_type_mapping){
                graph_type_mapping[jsonRes.type](graphId, jsonRes);
            }
            else{
                console.log("the report type '" + jsonRes.type + "' is not yet supported, sorry");
            }
        },
        error: function (err) {
            var jsonRes = err.responseJSON;
            var csrfToken = createReportItemForm.querySelector('input[name="csrfmiddlewaretoken"]');
            // update the report item graph
            createReportItemForm.innerHTML = csrfToken.outerHTML + jsonRes.report_form;

            // (re)link the changing of report_item type combobox to loading new parameters form
            // the name of the id is linked with the name of the attribute of ReportItem model in dashboard/models.py
            $("#id_report_type").change(function (event) {
                var reportItemType = $(this).val();
                updateReportItemParametersForm(reportItemType)
            })
            $("#id_scenarios").change(function (event) {
                var reportItemType = $("#id_report_type").val();
                updateReportItemParametersForm(reportItemType)
            })
        },
    })
}

function format_trace_name(scenario_name, label, unit, compare=false){
    title_label = format_as_title(label);
    var trace_name = title_label + ' (' + unit + ')' ;
    if(compare == true){
        trace_name = scenario_name + ' ' + trace_name;
    }
    return trace_name;

}


function format_as_title(label){
    title_string = (label.charAt(0).toUpperCase() + label.slice(1)).replace(/_/g, ' ');
    return title_string;
}


function addTimeseriesGraph(graphId, parameters){
    // prepare traces in plotly format
    var data = []

    var compare = true;
    if(parameters.data.length == 1){
        compare = false;
        parameters.title = "Scenario " + parameters.data[0].scenario_name;
    }

    parameters.data.forEach(scenario => {
        scenario.timeseries.forEach(timeseries => {
            var y_vals = timeseries.value;
            if(typeof y_vals === "string"){
                y_vals = JSON.parse(y_vals)
            }
            var trace = {x: scenario.timestamps,
                y: y_vals,
                name:"",
                type: 'scatter',
                line: {shape: 'hv'},
            };
            trace.name = format_trace_name(scenario.scenario_name, timeseries.label, timeseries.unit, compare=compare);
            data.push(trace);
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
        showlegend: true,
        hovermode:'x unified'
    }
    // create plot
    Plotly.newPlot(graphId, data, layout);
};

function addStackedTimeseriesGraph(graphId, parameters){
    // prepare stacked traces in plotly format
    var data = []
    var colorway = ["B2916C", "991818", "008753", "F2CD5D", "824670", "778EB5", "E86C1A"]
    var descriptions = parameters.descriptions
    if(parameters.data.length == 1){
        compare = false;
        parameters.title = parameters.title + " sector of scenario " + parameters.data[0].scenario_name;
    }
    axisRange = []

    parameters.data.forEach(scenario => {
        axisRange.push(scenario.timestamps[0], scenario.timestamps[168])
        scenario.timeseries.forEach(timeseries => {
            // todo provide a function to format the name of the timeseries
            var timeseriesName = timeseries.label + '_flow'
            var trace = {x: scenario.timestamps,
                y: timeseries.value,
                name: descriptions[timeseriesName].verbose,
                type: 'scatter',
                line: {shape: 'hv'},
                stackgroup: timeseries.group,
                fill: timeseries.fill,
                mode: timeseries.mode,
                customdata: Array(scenario.timestamps.length).fill([descriptions[timeseriesName].description]),
                hovertemplate: '<br><b>Value</b>: %{y:,.2f} kW<br>' + '<b>%{customdata}</b>',

            };
            data.push(trace);
        });
    });
    // prepare graph layout in plotly format
    const layout= {
//        title: parameters.title,
        xaxis:{
            title: parameters.x_label,
            range: axisRange
        },
        yaxis:{
            title: parameters.y_label,
        },
        hovermode:'x unified',
        colorway: colorway,
    }
    // create plot
    Plotly.newPlot(graphId, data, layout);
    saveToSession(graphId);
};

function storageResultGraph(x, ts_data, plot_id="",userLayout=null){

    // get the handle of the plotly plot
    if(plot_id == ""){
        plot_id = PLOT_ID;
    }
    var plotDiv = document.getElementById(plot_id);
    /* if the timestamps from the scenario are available, loads them
    var ts_timestamps_div = document.getElementById("input_timeseries_timestamps");
    if (ts_timestamps_div){
        var ts_timestamps = JSON.parse(ts_timestamps_div.querySelector("textarea").value);
        x = ts_timestamps
    }
    */

    // TODO add two y axis, one for charge/discharge and the other for SoC

    var plotLayout = {
        height: 220,
        margin:{
            b:45,
            l:60,
            r:60,
            t:15,
        },
        xaxis:{
            type: "date",
            title: timeseriesFlowTitle,
            autorange: "true",
        },
        yaxis:{
            title: timeseriesChargeDischargeTitle,
            autorange: "true",
        },
        yaxis2:{
            title: timeseriesCapacityTitle ,
            overlaying: "y",
            side: "right",
            autorange: "true",
        },
        legend: {orientation: "h"},
    };
    plotLayout = {...plotLayout, ...userLayout};
    var traces = [];
    var plot_y_axis = "y";
    for(var i=0; i<ts_data.length;++i){
        console.log(ts_data[i])
    // change legend layout
        plot_y_axis = (ts_data[i].name.includes("capacity") ? "y2" : "y");
        traces.push({type: "scatter", x: x, y: ts_data[i].value, name: ts_data[i].name + "(" + ts_data[i].unit + ")", yaxis: plot_y_axis});
    }

    Plotly.newPlot(plotDiv, traces, plotLayout, config);
    // simulate a click on autoscale
    plotDiv.querySelector('[data-title="Autoscale"]').click()
};

function plotTimeseries(x, ts_data, plot_id="",userLayout=null){

    // get the handle of the plotly plot
    if(plot_id == ""){
        plot_id = PLOT_ID;
    }
    var plotDiv = document.getElementById(plot_id);

    var plotLayout = {
        height: 220,
        margin:{
            b:45,
            l:60,
            r:60,
            t:15,
        },
        xaxis:{
            type: "date",
            title: timeseriesTimeTitle,
            autorange: "true",
        },
        yaxis:{
            title: timeseriesFlowTitle,
            autorange: "true",
        },
        legend: {orientation: "h"},
    };
    plotLayout = {...plotLayout, ...userLayout};
    var traces = [];
    var plot_y_axis = "y";
    var trace_label = "";
    for(var i=0; i<ts_data.length;++i){
        trace_label = "";
        console.log(ts_data[i]);
        if(ts_data[i].name){
            trace_label = ts_data[i].name;
            if(ts_data[i].unit){
                trace_label += "(" + ts_data[i].unit + ")";
            }
        };
        traces.push({type: "scatter", x: x, y: ts_data[i].value, name: trace_label , yaxis: plot_y_axis, ...ts_data[i].options});
    }

    Plotly.newPlot(plotDiv, traces, plotLayout, config);
    // simulate a click on autoscale
    plotDiv.querySelector('[data-title="Autoscale"]').click()
};



function addCapacitiyGraph(graphId, parameters){
    // prepare traces in ploty format
    var data = []
    var descriptions = parameters.descriptions
    // source of the palette: https://colorswall.com/palette/171311
    const colors = ["#F2CD5D"];
    const n_colors = colors.length;
    parameters.data.forEach((scenario,j) => {
        scenario.timeseries.forEach((timeseries,i) => {
            // todo provide a function to format the name of the timeseries
            data.push({
                x: scenario.timestamps,
                y: timeseries.capacity,
                name:timeseries.name,
                type: 'bar',
                offsetgroup: scenario.scenario_id,
                base: i==0 ? null : scenario.timeseries[0].capacity,
                customdata: Array(scenario.timestamps.length).fill([insertLineBreaks(descriptions[timeseries.name], 50)]),
                hovertemplate:  '<b>Capacity</b>: %{y:,.2f}'+ '<br><b>%{customdata}</b>',

//                marker: {color:colors[j%n_colors], pattern:{shape: i==0 ? "x" : ""}}

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
        showlegend: true,
        margin: {b: 150},
        colorway: colorway
    }
    // create plot
    Plotly.newPlot(graphId, data, layout);
};


function addCostGraph(graphId, parameters){
    // prepare traces in ploty format
    var data = []
    // source of the palette: https://colorswall.com/palette/171311
    const colors = ["#008753"];
    const patterns = ["", ".", "/", "x", "+", "-"]
    const n_colors = colors.length;
    parameters.data.forEach((scenario,j) => {
        scenario.timeseries.forEach((timeseries,i) => {
            // todo provide a function to format the name of the timeseries
            data.push({
                x: scenario.timestamps,
                y: timeseries.value,
                name:timeseries.name,
                text: timeseries.text,
                type: 'bar',
                offsetgroup: scenario.scenario_id,
                base: timeseries.base,
                marker: {color:colors[j%n_colors], pattern:{shape: patterns[i%6]}},
                customdata: timeseries.customdata,
                hovertemplate:timeseries.hover,
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
        showlegend: true,
        margin: {b: 150}
    }
    // create plot
    Plotly.newPlot(graphId, data, layout);
};


function addCostScenariosGraph(graphId, parameters){
    // prepare traces in ploty format
    var data = []
    // source of the palette: https://colorswall.com/palette/171311
    const colors = ["#d64e12", "#8bd346",  "#16a4d8",  "#efdf48", "#9b5fe0" , "#f9a52c", "#60dbe8"];
    const patterns = ["", ".", "/", "x", "+", "-"]
    const n_colors = colors.length;
    //parameters.data.forEach((scenario,j) => {
    parameters.data.forEach((timeseries,j) => {
//    console.log(scenario);
//        scenario.timeseries.forEach((timeseries,i) => {
            // todo provide a function to format the name of the timeseries
            data.push({
                x: timeseries.timestamps,
                //y: timeseries.value,
                y: timeseries.timeseries,
                //name:timeseries.name,
                name:timeseries.scenario_name,
               // text: timeseries.text,
                type: 'bar',
               // offsetgroup: scenario.scenario_id,
              //  base: timeseries.base,
               // marker: {color:colors[j%n_colors], pattern:{shape: patterns[i%6]}},
             //   customdata: timeseries.customdata,
              //  hovertemplate:timeseries.hover,
            })
//        });
    });

    // prepare graph layout in plotly format
    const layout= {
        title: parameters.title,
                barmode:'stack',
        xaxis:{
            title: parameters.x_label,
        },
        yaxis:{
            title: parameters.y_label,
        },
        showlegend: true,
        margin: {b: 150}
    }
    // create plot
    Plotly.newPlot(graphId, data, layout);
};

function addSankeyDiagram(graphId, parameters){
    // prepare graph layout in plotly format
    const layout= {
        title: parameters.title,
    }
    // create plot
    Plotly.newPlot(graphId, parameters.data.data, layout);
};

function addGenericPlotlyFigure(graphId, parameters){

    const fig = JSON.parse(parameters.data);
    // prepare graph layout in plotly format
    const layout= {
        title: parameters.title,
        ... fig.layout
    }
    // create plot
    Plotly.newPlot(graphId, fig.data, layout);
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
    Plotly.newPlot(graphId, parameters.data, layout);
};

function addFinancialPlot(parameters, plot_id="") {
	var plotDiv = document.getElementById(plot_id);
	var graphContents = parameters.graph_contents
	var layout = {
//        height: 220,
        margin:{
            b:100,
            l:100,
            r:100,
            t:100,
        },
        xaxis: {title: "Time"},
        yaxis: {title: "currency"},
        colorway: colorway,
        }
    var traces = [];
    for (const [key, value] of Object.entries(graphContents)) {
        trace = {
            type: "scatter",
            x: parameters.x,
            y: value.values,
            name: key,
            customdata: Array(parameters.x.length).fill([insertLineBreaks(value.description, 50)]),
            hovertemplate:  '<b>Value</b>: %{y:,.2f} NGN'+
            '<br><b>Year</b>: %{x}<br>'+
            '<b>%{customdata}</b>',
        };
    	traces.push(trace)
    }
    Plotly.newPlot(plotDiv, traces, layout, config);
    // simulate a click on autoscale
    plotDiv.querySelector('[data-title="Autoscale"]').click()
}

function addTable(response, table_id="") {

    var data = response.data;
    var headers = response.headers;
    const tableLength = Object.keys(headers).length + 1;
    var parentDiv = document.getElementById(table_id); // Get reference to the table element
    const table = document.createElement('table');
    // define table style
    table.classList.add("table", "table-bordered", "table-hover");
    const tableHead = document.createElement('thead');
    tableHead.classList.add("thead-dark")
    tableHead.style.position = "sticky"
    tableHead.style.top = "0"

    // create table header
    const tableHeadContent = document.createElement('tr');
    var tableHdr = document.createElement('th');
    tableHeadContent.appendChild(tableHdr);
    for (const [hdr, value] of Object.entries(headers)) {
        var tableHdr = document.createElement('th');
        tableHdr.class = "header_table"
        // omit unit if undefined
        if ((value.unit == undefined) || (value.unit == "")) {
            unit = " "
        }
        else {
            unit = ' (' + value.unit + ') '
        }
        if (value.description == undefined) {
            description = " "
            }
        else {
            description = value.description
        }
        tableHdr.innerHTML = value.verbose + unit + description;
        tableHeadContent.appendChild(tableHdr);
        };

    tableHead.appendChild(tableHeadContent);
    var tableBody = document.createElement('tbody');

    // create table body
    for (const [param, value] of Object.entries(data)) {
        const tableDataRow = document.createElement('tr');
        for (i=0; i < tableLength; ++i) {
            const tableDataCell = document.createElement('td');
            // omit unit if undefined
            if ((value.unit == undefined) || (value.unit == "")) {
            unit = " "
            }
            else {
                unit = ' (' + value.unit + ') '
            }
            // create the row title with unit and  description (help icon)
            if (i == 0) {
                tableDataCell.innerHTML = value.verbose + unit + value.description;
            }
            else {
                if (Array.isArray(value.value)) {
                tableDataCell.innerHTML = value.value[i-1]
                } else {
                tableDataCell.innerHTML = value.value
                }
            }
            tableDataRow.appendChild(tableDataCell);
            tableBody.appendChild(tableDataRow);
            }
        };

    table.appendChild(tableHead);
    table.appendChild(tableBody);
    parentDiv.appendChild(table);
    $('[data-bs-toggle="tooltip"]').tooltip()
}

function saveToSession(graphId) {
    // convert the plot to base64-encoded image
    const imageDataURL = Plotly.toImage(graphId, {format: 'png', width: 800, height: 500}).then(function(imageUrl) {
        $.ajax({
        headers: {'X-CSRFToken': csrfToken},
        type: 'POST',
        url: urlSaveToSession,
        data: {graph_id: graphId, image_url: imageUrl},
        success: function (response) {
            console.log(response);
        },
        error: function (error) {
            console.error(error);
        }
        });
    });
};

function downloadReport(proj_id) {
        $.ajax({
        headers: {'X-CSRFToken': csrfToken},
        type: 'POST',
        url: urlDownloadReport,
        data: {proj_id: proj_id},
        xhrFields: {responseType: 'blob'},
        success: function (response) {
            const link = document.createElement('a');
            link.href = URL.createObjectURL(response);
            link.download = 'report.docx';
            link.click();
        },
        error: function (error) {
            console.error(error);
        }
    });
};


function addPieChart(parameters, plot_id="") {
	var plotDiv = document.getElementById(plot_id);
    var labels = parameters.categories;
    var costs = parameters.costs;
    var descriptions = parameters.chart_descriptions.map(desc => insertLineBreaks(desc, 50))

    // Create a Plotly Pie Chart
    var data = [{
        labels: labels,
        values: costs,
        type: 'pie',
        customdata: descriptions,
        hovertemplate:  '<b>Category</b>: %{label}' +
        '<br><b>Value</b>: %{value:,.2f} NGN'+
        '<br><b>%{customdata}</b><extra></extra>',
        automargin: true
    }];

    var layout = {
        margin:{
            'b':100,
            'l':100,
            'r':100,
            't':100,
        },
        showlegend: true,
        colorway: colorway,
    };

    Plotly.newPlot(plotDiv, data, layout);
}


function addCostsChart(parameters, plot_id="") {
	var plotDiv = document.getElementById(plot_id);
    var assets = parameters.assets;
    var graphContents = parameters.graph_contents;
    var descriptions = parameters.descriptions;
    var data = []

    for (const [name, value] of Object.entries(graphContents)) {
        var trace = {
          x: assets,
          y: Object.values(value),
          name: name,
          type: 'bar',
          customdata: Array(assets.length).fill([descriptions[name]]),
          hovertemplate:  '<b>Costs</b>: %{y:,.2f} NGN'+
            '<br><b>Asset</b>: %{x}<br>'+
            '<b>%{customdata}</b>',
        };
        data.push(trace)
    }

    var layout = {
        margin:{
            'b':100,
            'l':100,
            'r':100,
            't':100,
        },
        barmode: 'stack',
        colorway: colorway,
    };

    Plotly.newPlot(plotDiv, data, layout);
}

function insertLineBreaks(inputString, charactersPerLine) {
//Note from Paula: This function was fully generated with ChatGPT
    // Split the input string into an array of words
    var words = inputString.split(' ');

    // Initialize an empty string to store the result
    var result = '';

    // Initialize a variable to keep track of the number of characters in the current line
    let currentLineLength = 0;

    // Loop through the words array
    for (let i = 0; i < words.length; i++) {
        // Get the current word
        let word = words[i];

        // Add the current word to the result string
        result += word + ' ';

        // Update the current line length with the length of the current word
        currentLineLength += word.length + 1;

        // Check if the current line length exceeds the specified characters per line
        if (currentLineLength > charactersPerLine) {
            // If exceeded, add a line break and reset the current line length
            result += '<br>';
            currentLineLength = 0;
        }
    }

    // Return the result string with line breaks inserted
    return result.trim(); // Trim to remove any extra spaces at the end
}


// TODO write functions for other report types
var graph_type_mapping={
    timeseries: addTimeseriesGraph,
    timeseries_stacked: addStackedTimeseriesGraph,
    timeseries_stacked_cpn: addStackedTimeseriesGraph,
    capacities: addCapacitiyGraph,
    costs: addCostGraph,
    costsScenarios: addCostScenariosGraph,
    sensitivity_analysis: addSensitivityAnalysisGraph,
    sankey: addSankeyDiagram,
    load_duration: addGenericPlotlyFigure
}
// # GRAPH_TIMESERIES = "timeseries"
// # GRAPH_TIMESERIES_STACKED = "timeseries_stacked"
// # GRAPH_TIMESERIES_STACKED = "timeseries_stacked_cpn"
// # GRAPH_CAPACITIES = "capacities"
// # GRAPH_BAR = "bar"
// # GRAPH_PIE = "pie"
// # GRAPH_LOAD_DURATION = "load_duration"
// # GRAPH_SANKEY = "sankey"


var existingReportItemsData = JSON.parse(document.getElementById('existingReportItemsData').textContent);
if(existingReportItemsData != "") {
    existingReportItemsData.forEach(reportItem => {
        var graphId = addReportItemGraphToDOM(reportItem);
        if (reportItem.type in graph_type_mapping) {
            graph_type_mapping[reportItem.type](graphId, reportItem);
        } else {
            console.log("the report type '" + reportItem.type + "' is not yet supported, sorry");
        }

    });
}
