/*jshint esversion: 11 */
/*jshint sub:true*/

// Constants
const ASSET_TYPE_NAME = 'asset_type_name';
const BUS = "bus";
// UUID to Drawflow Id Mapping
// const nodeToDbId = { 'bus': [], 'asset': [] };
const nodesToDB = new Map();
const guiModalDOM = document.getElementById("guiModal");
const guiModal = new bootstrap.Modal(guiModalDOM, {backdrop: 'static'});

var copCollapseDOM = document.getElementById('form-computeCOP');
if(copCollapseDOM){
    var copCollapse = new bootstrap.Collapse(copCollapseDOM);
    // refresh the field of the projects/forms.py::COPCalculatorForm to plot the data if any
    copCollapseDOM.addEventListener('shown.bs.collapse', function () {
        const tHighDOM = guiModalDOM.querySelector('input[name="temperature_high_scalar"]');
        if(tHighDOM)
            tHighDOM.dispatchEvent(new Event('change'));
        const tLowDOM = guiModalDOM.querySelector('input[name="temperature_low_scalar"]');
         if(tLowDOM)
            tLowDOM.dispatchEvent(new Event('change'));
    });
}


// Initialize Drawflow
const id = document.getElementById("drawflow");
const editor = new Drawflow(id);
editor.reroute = true;
editor.start();
// editor.drawflow.drawflow.Home.data; // All node level data are saved here

/* Mouse and Touch Actions */
for (let element of document.getElementsByClassName('drag-drawflow')) {
    element.addEventListener('touchend', drop, false);
    element.addEventListener('touchstart', drag, false);
}
for (let element of document.getElementsByClassName('section__component')) {
    element.addEventListener('touchend', drop, false);
    element.addEventListener('touchstart', drag, false);
}

function allowDrop(ev) {
    ev.preventDefault();
}

function drag(ev) {
    // corresponds to data-node defined in templates/scenario/topology_drag_items.html
    ev.dataTransfer.setData("node", ev.target.getAttribute('data-node'));
}

function drop(ev) {
    ev.preventDefault();
    // corresponds to data-node defined in templates/scenario/topology_drag_items.html
    const nodeName = ev.dataTransfer.getData("node");
    addNodeToDrawFlow(nodeName, ev.clientX, ev.clientY).then(node => {
        // after adding node, try to save node with default data
        // populate form and submit
        node = document.getElementById('node-' + node.editorNodeId);
        populateForm(node, submit=true);
    });
}


// Disallow Any Connection to be created without a bus.
editor.on('connectionCreated', function (connection) {
    var nodeIn = editor.getNodeFromId(connection.input_id);
    var nodeOut = editor.getNodeFromId(connection.output_id);
    if ((nodeIn.name !== BUS && nodeOut.name !== BUS) || (nodeIn.name === BUS && nodeOut.name === BUS)) {
        editor.removeSingleConnection(connection.output_id, connection.input_id, connection.output_class, connection.input_class);
        Swal.fire('Unexpected Connection', 'Please connect assets to each other\n only through a bus node. Interconnecting busses is also not allowed.', 'error');
    }
    // change: enable save button
    document.getElementById('btn-save')?.classList.remove('disabled');
});

editor.on('connectionRemoved', _ => {
    // change: enable save button
    document.getElementById('btn-save')?.classList.remove('disabled');
});

editor.on('nodeCreated', _ => {
    // change: enable save button
    document.getElementById('btn-save')?.classList.remove('disabled');
});

editor.on('nodeMoved', _ => {
    // change: enable save button
    document.getElementById('btn-save')?.classList.remove('disabled');
});

editor.on('nodeRemoved', function (nodeID) {
    // remove nodeID from nodesToDB
    nodesToDB.delete('node-'+nodeID);
    // change: enable save button
    document.getElementById('btn-save')?.classList.remove('disabled');
});


async function addNodeToDrawFlow(name, pos_x, pos_y, nodeInputs = 1, nodeOutputs = 1, nodeData = {}) {
    if (editor.editor_mode === 'fixed')
        return false;
    pos_x = pos_x * (editor.precanvas.clientWidth / (editor.precanvas.clientWidth * editor.zoom)) - (editor.precanvas.getBoundingClientRect().x * (editor.precanvas.clientWidth / (editor.precanvas.clientWidth * editor.zoom)));
    pos_y = pos_y * (editor.precanvas.clientHeight / (editor.precanvas.clientHeight * editor.zoom)) - (editor.precanvas.getBoundingClientRect().y * (editor.precanvas.clientHeight / (editor.precanvas.clientHeight * editor.zoom)));
    return createNodeObject(name, pos_x, pos_y, nodeInputs, nodeOutputs, nodeData);
}

// TODO potentially remove this function
function updateInputTimeseries(){
    //connected to the templates/asset/asset_create_form.html content
    /*ts_data_div = document.getElementById("input_timeseries_data");
    if(ts_data_div){
        var ts_data = JSON.parse(ts_data_div.querySelector("textarea").value);
        var ts_data = ts_data.map(String);
        var ts_idx = [...Array(ts_data.length).keys()];
        ts_idx = ts_idx.map(String);
        makePlotly( ts_idx, ts_data, plot_id="timeseries_trace")
    }*/
}

// find out the name of the other nodes the given node is connected to
function getInputOutputMapping(nodeId){
    var input_output_mapping = {"inputs": {}, "outputs": {}};
    editor.getNodeFromId(nodeId).inputs.input_1.connections.map(c => {const nodeIn = editor.getNodeFromId(parseInt(c.node)); input_output_mapping.inputs[nodeIn.data.bustype] = nodeIn.data.name;});
    editor.getNodeFromId(nodeId).outputs.output_1.connections.map(c => {const nodeOut = editor.getNodeFromId(parseInt(c.node)); input_output_mapping.outputs[nodeOut.data.bustype] = nodeOut.data.name;});
    input_output_mapping.inputs = JSON.stringify(input_output_mapping.inputs);
    input_output_mapping.outputs = JSON.stringify(input_output_mapping.outputs);

    return input_output_mapping;
}

// COP calculation from temperature
function toggle_cop_modal(event){
    // get the parameters which uniquely identify the asset
    const assetTypeName = guiModalDOM.getAttribute("data-node-type");
    const topologyNodeId = guiModalDOM.getAttribute("data-node-topo-id"); // e.g. 'node-2'

    let getUrl = copGetUrl + assetTypeName;
    if (nodesToDB.has(topologyNodeId))
        getUrl += "/" + nodesToDB.get(topologyNodeId).uid;

    fetch(getUrl).then(response => response.text()).then(formContent => {
        // assign the content of the form to the form tag of the modal
        guiModalDOM.querySelector('form .modal-addendum').innerHTML = formContent;
    }).catch(error => {
        console.error(error);
    });
}

// function to compute the COP of a heat pump linked with the button of id="btn-computeCOP" in templates/scenario//scenario_step2.html
function computeCOP(event){

    // get the parameters which uniquely identify the asset
    const assetTypeName = guiModalDOM.getAttribute("data-node-type");
    const topologyNodeId = guiModalDOM.getAttribute("data-node-topo-id"); // e.g. 'node-2'

    const copForm = event.target.closest('.modal-content').querySelector('#copForm');
    const formData = new FormData(copForm);

  // copPostUrl is defined in scenario_step2.html
    let postUrl = copPostUrl + assetTypeName;
    if (nodesToDB.has(topologyNodeId))
        postUrl += "/" + nodesToDB.get(topologyNodeId).uid;

    // send the form of the asset to be saved in database (projects/views.py::asset_cops_create_or_update)
    fetch(postUrl, {
        method: 'POST',
        headers: {'X-CSRFToken': csrfToken},
        body: formData,
    }).then(response => response.json()).then(jsonRes => {
        if (jsonRes.success) {
            // close the cop area
            copCollapse.hide();

            efficiencyDOM = guiModalDOM.querySelector('input[name="efficiency_scalar"]');
            if(efficiencyDOM){
                efficiencyDOM.value = jsonRes.cops;
                efficiencyDOM.dispatchEvent(new Event('change'));
            }
            copDOM = guiModalDOM.querySelector('input[name="copId"]');
            if(copDOM){
                copDOM.value = jsonRes.cop_id;
            }
        } else {
            // not success: assign the content of the form to the form tag of the modal
            guiModalDOM.querySelector('form .modal-addendum').innerHTML = jsonRes.form_html;
        }
    }).catch(error => {
        console.error(error);
        alert(error.message);
    });
}


function populateForm(node, submit=false) {
    // populate modal form with node data
    // optionally immediately submit form without showing
    if (!node)
        return;
    const nodeType = node.querySelector('.box').getAttribute(ASSET_TYPE_NAME);
    const topologyNodeId = node.id;

    const nodeId = parseInt(topologyNodeId.split("-").pop());
    const input_output_mapping = getInputOutputMapping(nodeId);
    // formGetUrl is defined in scenario_step2.html
    let getUrl = formGetUrl + nodeType;
    if (nodesToDB.has(topologyNodeId))
        getUrl += "/" + nodesToDB.get(topologyNodeId).uid;
    // add input_output_mapping as GET parameters
    getUrl += '?' + new URLSearchParams(input_output_mapping);

    // get the form of the asset of the type "nodeType" (projects/views.py::get_asset_create_form)
    fetch(getUrl).then(response => response.text()).then(formContent => {
        // assign the content of the form to the form tag of the modal
        guiModalDOM.querySelector('form .modal-body').innerHTML = formContent;

        // set parameters which uniquely identify the asset
        guiModalDOM.setAttribute("data-node-type", nodeType);
        guiModalDOM.setAttribute("data-node-topo-id", topologyNodeId);
        guiModalDOM.setAttribute("data-node-df-id", topologyNodeId.split("-").pop());

        updateInputTimeseries();

        if (submit)
            submitForm();
        else
            guiModal.show();

        if(copCollapseDOM){
            copCollapse.hide();
        }
        $('[data-bs-toggle="tooltip"]').tooltip();
    }).catch(error => {
        alert("Could not open node:\n"+error.message);
        console.error(error);
    });
}

// callback for double-clicking on node in editor
// add with eventListener (<some jquery div>.addEventListener("dblclick", dblClick))
function dblClick(e) {
    const closestNode = e.target.closest('.drawflow-node');
    populateForm(closestNode);
}

/* onclick method associated to the save button of the modal */
function submitForm() {

    // get the parameters which uniquely identify the asset
    const assetTypeName = guiModalDOM.getAttribute("data-node-type");
    const topologyNodeId = guiModalDOM.getAttribute("data-node-topo-id"); // e.g. 'node-2'
    const drawflowNodeId = guiModalDOM.getAttribute("data-node-df-id");

    // get the node name field to update it if the form was submitted successfully
    const nodeName = document.getElementById(topologyNodeId).querySelector(".nodeName");
    const nodeNameValue = guiModalDOM.querySelector('input[df-name]').value;
    // get the data of the form
    const assetForm = document.getElementById('assetForm');
    const formData = new FormData(assetForm);

    // add the XY position of the node to the form data
    const nodePosX = editor.drawflow.drawflow.Home.data[drawflowNodeId].pos_x;
    const nodePosY = editor.drawflow.drawflow.Home.data[drawflowNodeId].pos_y;
    formData.set('pos_x', nodePosX);
    formData.set('pos_y', nodePosY);

    // if the asset is a bus, add the input and output ports to the form data
    if (assetTypeName === BUS) {
        const nodeInputs = Object.keys(editor.drawflow.drawflow.Home.data[drawflowNodeId].inputs).length;
        const nodeOutputs = Object.keys(editor.drawflow.drawflow.Home.data[drawflowNodeId].outputs).length;
        formData.set('input_ports', nodeInputs);
        formData.set('output_ports', nodeOutputs);
    }
    else {
        const nodeId = parseInt(topologyNodeId.split("-").pop());
        const input_output_mapping = getInputOutputMapping(nodeId);
        formData.set("inputs", input_output_mapping.inputs);
        formData.set("outputs", input_output_mapping.outputs);
    }

    // formPostUrl is defined in scenario_step2.html
    let postUrl = formPostUrl + assetTypeName;
    if (nodesToDB.has(topologyNodeId))
        postUrl += "/" + nodesToDB.get(topologyNodeId).uid;

    // send the form of the asset to be saved in database (projects/views.py::asset_create_or_update)
    fetch(postUrl, {
        method: 'POST',
        headers: {'X-CSRFToken': csrfToken},
        body: formData,
    }).then(response => response.json()).then(jsonRes => {
        if (jsonRes.success) {
            // rename the node on the fly (to avoid the need of refreshing the page)
            nodeName.textContent = nodeNameValue;

            // add the node id to the nodesToDB mapping
            if (!nodesToDB.has(topologyNodeId))
                nodesToDB.set(topologyNodeId, {uid:jsonRes.asset_id, assetTypeName: assetTypeName });

            guiModal.hide();
            if(copCollapseDOM){
                copCollapse.hide();
            }
        } else {
            // assign the content of the form to the form tag of the modal
            guiModalDOM.querySelector('form .modal-body').innerHTML = jsonRes.form_html;
            // make certain to show form
            guiModal.show();
        }
    }).catch(error => {
        console.error(error);
        alert(error.message);
    });
}

$("#guiModal").on('shown.bs.modal', _ => {
     var formDiv = document.getElementsByClassName("form-group");
     var plotDiv = null;

    //TODO get rid of maybe soc_traces
     var plotDivIds = ["flow_trace", "soc_traces"];

     for(i=0;i<plotDivIds.length;++i){
         plotDiv = document.getElementById(plotDivIds[i]);
         if (plotDiv){
            Plotly.relayout(plotDiv, {width: plotDiv.clientWidth});
         }
     }
     const evt = new Event("change");
	 // look only for the form with the provided class to be extra safe
	 document.querySelectorAll("input[name$='_scalar']").forEach(node => { node.dispatchEvent(evt); });
});

/* Triggered before the modal opens */
$("#guiModal").on('show.bs.modal', function (event) {
  var modal = $(event.target);
  // rename the node on the fly (to avoid the need of refreshing the page)
  const nodeName = guiModalDOM.querySelector('input[df-name]');
  if(nodeName){
    modal.find('.modal-title').text(nodeName.value.replaceAll("_", " "));
  }
  editor.editor_mode = "fixed";
});

/* Triggered before the modal hides */
$("#guiModal").on('hide.bs.modal', function (event) {
  // reset the modal form to empty
  guiModalDOM.querySelector('form .modal-body').innerHTML = "";
  editor.editor_mode = "edit";
});


/* Create node on the gui */
async function createNodeObject(nodeName, pos_x, pos_y, connectionInputs = 1, connectionOutputs = 1, nodeData = {}) {
    // automate the naming of assets to avoid name duplicates
    const editorData = editor.export().drawflow.Home.data;
    const node_list = Object.values(editorData);
    const node_classes = node_list.map(obj => obj.class);
    let existing_items = node_classes.reduce((acc, name) => acc+name.includes(nodeName), 0);

    let shownName;
    if(typeof nodeData.name === "undefined"){
        if(existing_items == 0){
            shownName = nodeName + "-0";
        }
        else{
            shownName = nodeName + "-" + existing_items;
        }
        nodeData.name = shownName;
    }
    else{
        shownName = nodeData.name;
    }

    const source_html = `<div class="box" ${ASSET_TYPE_NAME}="${nodeName}">
    </div>

    <div class="drawflow-node__name nodeName">
        <span>
          ${shownName}
        </span>
    </div>
    <div class="img"></div>`;

    return {
        "editorNodeId": editor.addNode(nodeName, connectionInputs, connectionOutputs, pos_x, pos_y, nodeName, nodeData, source_html),
        "specificNodeType": nodeName
    };
}


/* Script to retrieve nodes (assets and busses) and links data from the backend. */
/* Html of asset modification is provided in grid_model_topology.js:createNodeObject function */
async function addBusses(data) {
    await Promise.all(data.map(async nodeData => {
        const result = await createNodeObject(nodeData.name, nodeData.pos_x, nodeData.pos_y, nodeData.input_ports, nodeData.output_ports, nodeData.data);
        nodesToDB.set(`node-${result.editorNodeId}`, {uid:nodeData.data.databaseId, assetTypeName: "bus" });
    }));
}
async function addAssets(data) {
    await Promise.all(data.map(async nodeData => {
        const result = await createNodeObject(nodeData.name, nodeData.pos_x, nodeData.pos_y, 1, 1, nodeData.data);
        nodesToDB.set(`node-${result.editorNodeId}`, {uid:nodeData.data.unique_id, assetTypeName: nodeData.name });
    }));
}

/* 'editor' is the variable name of the DrawFlow instance used here as a global variable */
async function addLinks(data) {
    data.map(async linkData => {
        const busNodeId = [...nodesToDB.entries()].filter(([key,val])=>val.uid===linkData.bus_id).map(([k,v])=>k)[0].split("-").pop();
        const assetNodeId = [...nodesToDB.entries()].filter(([key,val])=>val.uid===linkData.asset_id).map(([k,v])=>k)[0].split("-").pop();
        if (linkData.flow_direction === "B2A")
            editor.addConnection(busNodeId, assetNodeId, linkData.bus_connection_port, 'input_1');
        else
            editor.addConnection(assetNodeId, busNodeId, 'output_1', linkData.bus_connection_port);
    });
}

function zoomToFit() {
    const nodeWidth = 152;
    const nodeHeight = 128;

    const nodes = Object.values(editor.drawflow.drawflow.Home.data); // Array with all nodes

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

    // get outer most node bounding box edges
    nodes.forEach(node => {
        minX = Math.min(minX, node.pos_x);
        minY = Math.min(minY, node.pos_y);
        maxX = Math.max(maxX, node.pos_x + nodeWidth);
        maxY = Math.max(maxY, node.pos_y + nodeHeight);
    });
    const nodesWidth = maxX - minX;
    const nodesHeight = maxY - minY;

    // get space of editor
    const editorElem = document.querySelector('.drawflow');
    const editorWidth = editorElem.clientWidth;
    const editorHeight = editorElem.clientHeight;

    // calculate zoom
    const zoomX = editorWidth / (nodesWidth + 2);
    const zoomY = editorHeight / (nodesHeight + 2);
    const zoom = Math.min(zoomX, zoomY, 1); // max 1 (no zoom)
    editor.zoom = zoom;

    // center editor
    const offsetX = (editorWidth - nodesWidth * zoom) / 2 - minX * zoom;
    const offsetY = (editorHeight - nodesHeight * zoom) / 2 - minY * zoom;
    editor.precanvas.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${zoom})`;
}
