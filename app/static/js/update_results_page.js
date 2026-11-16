$(document).ready(function () {
    const scen_id = "{{ scen_id }}";
    const proj_id = "{{ proj_id }}";
});

function update_kpi_table_style(scen_id="", table_id="summary"){
    $.ajax({
        url: urlRequestKPITable + "?compare_scenario=" + scen_id,
        type: "GET",
        data: {table_id: table_id},
        success: async (table_data) => {
            await addSummaryTable(table_data, table_id);
        }
    });
}

function addSummaryTable(table_data, table_id) {
    let parentDiv = document.getElementById(table_id + "Table");
    parentDiv.innerHTML = "";

    /* create KPI table headers */
    parentDiv.classList.add("table-bordered", "table-hover");
    let tableHead = document.createElement('thead');
    tableHead.classList.add("thead-dark");
    tableHead.style.position = "sticky";
    tableHead.style.top = "0";
    let table_headers = table_data.hdrs;
    let table_length = table_headers.length;
    let tableHeadContent = document.createElement('tr');
    table_headers.map(hdr =>
        {
            var tableHdr = document.createElement('th');
            tableHdr.innerHTML = hdr;
            tableHeadContent.appendChild(tableHdr);
        }
    );
    tableHead.appendChild(tableHeadContent);
    parentDiv.appendChild(tableHead);


    for (let subBody in table_data.data) {
        let tableBody = document.createElement('tbody');
        tableBody.id = subBody;

        if (Object.keys(table_data.data).length  > 1) {
            /* add subtable title */
            const tableSubSectionTitleRow = document.createElement('tr');
            let tableSubSectionTitle = document.createElement('th');
            tableSubSectionTitle.colSpan = table_length;
            tableSubSectionTitle.innerHTML = subBody;
            tableSubSectionTitle.style.padding = "0.5rem";
            tableSubSectionTitleRow.appendChild(tableSubSectionTitle);
            for(let i=0;i<table_length-1;i += 1){
                tableSubSectionTitleRow.appendChild(document.createElement('td'));
            }
                tableBody.appendChild(tableSubSectionTitle);
            }

        /* add subtable lines for each parameter */
        // (param should be a json object) with keys name (type str), unit type (str) and scen_values
        /* jshint -W083 */
        table_data.data[subBody].forEach(param =>{
            let tableSubSectionParamRow = document.createElement('tr');
            let cell = tableSubSectionParamRow.insertCell(0);
            cell.innerHTML = param.name + param.description;
            //cell.setAttribute("title", param.description)
            //cell.append(" just to see");
            // todo for loop over scenario values
            for (let i=0;i<param.scen_values.length;i += 1){
                cell = tableSubSectionParamRow.insertCell(1 + i);
                cell.innerHTML = param.scen_values[i] +" " + param.unit;
            }
            tableBody.appendChild(tableSubSectionParamRow);
        });


        parentDiv.appendChild(tableBody);
    }
    $('[data-bs-toggle="tooltip"]').tooltip();

}


function addWideTable(table_data, table_id){
    let parentDiv = document.getElementById(table_id + "Table");
    let titleDiv = document.getElementById(table_id + "TableTitle");
    titleDiv.innerHTML = table_data.title;
    parentDiv.innerHTML = "";

    /* create KPI table headers */
    parentDiv.classList.add("table-bordered", "table-hover");
    let tableHead = document.createElement('thead');
    tableHead.classList.add("thead-dark");
    tableHead.style.position = "sticky";
    tableHead.style.top = "0";
    let table_headers = table_data.hdrs; // todo add dynamically more scenarios here
    let table_length = table_headers.length + 1;
    let tableHeadContent = document.createElement('tr');
    // Add first (empty) header
    tableHeadContent.appendChild(document.createElement('th'));
    table_headers.map(hdr =>
        {
            var tableHdr = document.createElement('th');
            tableHdr.innerHTML = hdr;
            tableHeadContent.appendChild(tableHdr);
        }
    );
    tableHead.appendChild(tableHeadContent);
    parentDiv.appendChild(tableHead);

    // --- build table body ---
    const tableBody = document.createElement('tbody');

    for (const [key, entry] of Object.entries(table_data.data)) {
        const value = {
            verbose: entry.name,
            description: entry.description || "",
            unit: entry.unit || "",
            value: entry.scen_values
        };

        const tableDataRow = document.createElement('tr');

        for (let i = 0; i < table_length; i += 1) {
            const tableDataCell = document.createElement('td');

            let unit = (value.unit === "" ? " " : " (" + value.unit + ") ");

            if (i === 0) {
                // row title
                tableDataCell.innerHTML = value.verbose + unit + value.description;
            } else {
                if (Array.isArray(value.value)) {
                    tableDataCell.innerHTML = value.value[i - 1];
                } else {
                    tableDataCell.innerHTML = value.value;
                }
            }
            // highlight totals
            if (value.verbose.toLowerCase().includes("total")) {
                tableDataCell.style.fontWeight = "bold";
                tableDataCell.style.backgroundColor = "#F9F8F7";
            }

            tableDataRow.appendChild(tableDataCell);
        }

        tableBody.appendChild(tableDataRow);
    }

    // --- append everything ---
    parentDiv.appendChild(tableHead);
    parentDiv.appendChild(tableBody);

    // enable Bootstrap tooltips if any
    $('[data-bs-toggle="tooltip"]').tooltip();
}
/*error: function (xhr, errmsg) {
    console.log("backend_error!")
    //Show the error message
    $('#message-div').html("<div class='alert-error'>" +
        "<strong>Success: </strong> We have encountered an error: " + errmsg + "</div>");
}*/

function request_results_table(scen_id="", table_id=""){
 $.ajax({
            url: urlRequestResultsTable + scen_id + "/" + table_id,
            type: "GET",
            success: async (table_data) => {
                await addWideTable(table_data, table_id=table_id);
            },
        });
    }

/* loop over scenario selection buttons and return the ids of the selected ones */
function fetchSelectedScenarios(){
    var selectedScenarios = [];
    var scenariosDropDown = $("#results-scenarios");
    if(scenariosDropDown){
        if(Array.isArray(scenariosDropDown.val()) == false){
            selectedScenarios.push(scenariosDropDown.val().split("-")[2]);
        }
        else{
            selectedScenarios = scenariosDropDown.val();
        }
    }
    return selectedScenarios;
}

function translateLabel(label) {
    return typeof label === "string" ? gettext(label) : label;
}

function translateFigureLabels(data, layout) {
    // try and get all strings that might need translation across different chart types
    data.forEach(trace => {
        if (trace.name) trace.name = gettext(trace.name);
        if (Array.isArray(trace.x)) trace.x = trace.x.map(translateLabel);
        if (Array.isArray(trace.y)) trace.y = trace.y.map(translateLabel);
        if (Array.isArray(trace.labels)) trace.labels = trace.labels.map(translateLabel);
    });

    if (layout?.title?.text) layout.title.text = gettext(layout.title.text);
    if (layout?.legend?.title?.text) layout.legend.title.text = gettext(layout.legend.title.text);

    Object.keys(layout || {})
        .filter(key => /^[xy]axis\d*$/.test(key))
        .forEach(axisKey => {
            const axis = layout[axisKey];
            if (axis?.title?.text) axis.title.text = gettext(axis.title.text);
            if (Array.isArray(axis?.categoryarray)) {
                axis.categoryarray = axis.categoryarray.map(translateLabel);
            }
        });
}

function insertPlotlyGraph(graphId, data, layout){
    console.log(data);
    console.log(layout);
//    //translateFigureLabels(data, layout);
//
//    // finds the title of the section
//    const graph = document.getElementById(`graph-${graphId}`);
//    const title = graph
//    .closest(".chart")
//    .querySelector(".chart__header .title a");
//
//    // replaces section title by the graph title
//    // title.textContent = gettext(layout.title.text);
//    // erases graph title
//    layout.title.text = "";
    Plotly.newPlot(
        "graph-" + graphId,
        data,
        layout
    );
}

function scenario_visualize_timeseries(scen_id=""){
    scenario_visualize_given_graph(scen_id, variable="timeseries");
}

async function scenario_visualize_given_graph(scen_id = "", variable = "") {
    const url =
        `${urlVisualizeAnyGraph}` +
        `${scen_id ? `${encodeURIComponent(scen_id)}/` : ""}` +
        `${encodeURIComponent(variable)}`;

    try {
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const figure = await response.json();

        await insertPlotlyGraph(
            figure.id,
            figure.data,
            figure.layout
        );
    } catch (error) {
        console.error("Could not load graph:", error);
    }
}

function scenario_visualize_stacked_timeseries(scen_id){
 $.ajax({
            url: urlVisualizeStackedTimeseries  + scen_id,
            type: "GET",
            success: async (graphs) => {
                const parentDiv = document.getElementById("stacked_timeseries");
                await graphs.map(parameters => {
                    const newGraph = document.createElement('div');
                    newGraph.id = "stacked_timeseries" + parameters.id;
                    parentDiv.appendChild(newGraph);
                    graph_type_mapping[parameters.type](newGraph.id, parameters);
                });
            },
        });
}


function scenario_visualize_sankey(scen_id, ts=null){
	var urlParams = scen_id;
	if( ts === null || ts === ""){
	}
	else{
		urlParams = scen_id + "/" + ts;
	}
    $.ajax({
        url: urlVisualizeSankey + urlParams,
        type: "GET",
        success: async (figure) => {
            await insertPlotlyGraph(figure.id, figure.data,figure.layout);
        },
    });
}

function scenario_visualize_capacities(scen_id=""){
    scenario_visualize_given_graph(scen_id, variable="capacities");
}

function scenario_visualize_costs(scen_id=""){
    scenario_visualize_given_graph(scen_id, variable="costs");
}
