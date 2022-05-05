// Constants
const ASSET_TYPE_NAME = 'asset_type_name';
const BUS = "bus";
// UUID to Drawflow Id Mapping
// const nodeToDbId = { 'bus': [], 'asset': [] };
const nodesToDB = new Map();
var guiModalDOM = document.getElementById("guiModal");
var guiModal = new bootstrap.Modal(guiModalDOM);



// Initialize Drawflow
const id = document.getElementById("drawflow");
const editor = new Drawflow(id);
editor.reroute = true;
editor.start();
// editor.drawflow.drawflow.Home.data; // All node level data are saved here

/* Mouse and Touch Actions */
var elements = document.getElementsByClassName('drag-drawflow');
for (let i = 0; i < elements.length; i++) {
    elements[i].addEventListener('touchend', drop, false);
    elements[i].addEventListener('touchstart', drag, false);
}
var elements = document.getElementsByClassName('section__component');
for (let i = 0; i < elements.length; i++) {
    elements[i].addEventListener('touchend', drop, false);
    elements[i].addEventListener('touchstart', drag, false);
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
    (nodeName === BUS) ? IOBusOptions(nodeName, ev.clientX, ev.clientY)
        : addNodeToDrawFlow(nodeName, ev.clientX, ev.clientY);
}


function IOBusOptions(nodeName, posX, posY) {
    const checkMinMax = (value, min, max) => (value <= min) ? min : (value >= max) ? max : value;
    Swal.mixin({
        input: 'number',
        confirmButtonText: 'Next',
        showCancelButton: true,
        progressSteps: ['1', '2']
    })
        .queue([
            {
                title: 'Bus Inputs',
                text: 'Provide the number of bus Inputs (default 1)',
            },
            {
                title: 'Bus Outputs',
                text: 'Provide the number of bus Outputs (default 1)',
            }
        ])
        .then((result) => {
            if (result.value) {
                const inputs = checkMinMax(result.value[0], 1, 7);
                const outputs = checkMinMax(result.value[1], 1, 7);
                addNodeToDrawFlow(nodeName, posX, posY, inputs, outputs);
            }
        })
}


// Disallow Any Connection to be created without a bus.
editor.on('connectionCreated', function (connection) {
    var nodeIn = editor.getNodeFromId(connection['input_id']);
    var nodeOut = editor.getNodeFromId(connection['output_id']);
    if ((nodeIn['name'] !== BUS && nodeOut['name'] !== BUS) || (nodeIn['name'] === BUS && nodeOut['name'] === BUS)) {
        editor.removeSingleConnection(connection['output_id'], connection['input_id'], connection['output_class'], connection['input_class']);
        Swal.fire('Unexpected Connection', 'Please connect assets to each other\n only through a bus node. Interconnecting busses is also not allowed.', 'error')
    }
})

// might be redundant
editor.on('nodeCreated', function (nodeID) {
    // region bind installed_capacity to age_installed Changes
    // const nodeIdInstalledCapInput = document.getElementById(`node-${nodeID}`).querySelector("input[name='installed_capacity']");
    // if (nodeIdInstalledCapInput) {
    //     nodeIdInstalledCapInput.addEventListener('change', function (e) {
    //         const ageInstalledElement = e.target.closest("#FormGroup").querySelector("input[name='age_installed']");
    //         if (e.target.value === '0') {
    //             ageInstalledElement.value = '0';
    //             ageInstalledElement.readOnly = true;
    //             let notifyAgeInputEvent = new Event("input", { bubbles: true });
    //             ageInstalledElement.dispatchEvent(notifyAgeInputEvent);
    //         } else
    //             ageInstalledElement.readOnly = false;
    //     });
    //     // for existing nodes check if installed cap is zero and set age_installed to read only
    //     if (nodeIdInstalledCapInput.value === '0')
    //         nodeIdInstalledCapInput.closest("#FormGroup").querySelector("input[name='age_installed']").readOnly = true;
    // }
    // endregion
})

editor.on('nodeRemoved', function (nodeID) {
    // remove nodeID from nodesToDB
    nodesToDB.delete('node-'+nodeID);
})


async function addNodeToDrawFlow(name, pos_x, pos_y, nodeInputs = 1, nodeOutputs = 1, nodeData = {}) {
    if (editor.editor_mode === 'fixed')
        return false;
    pos_x = pos_x * (editor.precanvas.clientWidth / (editor.precanvas.clientWidth * editor.zoom)) - (editor.precanvas.getBoundingClientRect().x * (editor.precanvas.clientWidth / (editor.precanvas.clientWidth * editor.zoom)));
    pos_y = pos_y * (editor.precanvas.clientHeight / (editor.precanvas.clientHeight * editor.zoom)) - (editor.precanvas.getBoundingClientRect().y * (editor.precanvas.clientHeight / (editor.precanvas.clientHeight * editor.zoom)));
    return createNodeObject(name, nodeInputs, nodeOutputs, nodeData, pos_x, pos_y);
    // return createNodeObject(name, nodeInputs, nodeOutputs, {}, pos_x, pos_y); was like that
}

document.addEventListener("dblclick", function (e) {

    const closestNode = e.target.closest('.drawflow-node');
    const nodeType = closestNode.querySelector('.box').getAttribute(ASSET_TYPE_NAME);

    if (closestNode) {
        const topologyNodeId = closestNode.id;
        // formGetUrl is defined in scenario_step2.html
        const getUrl = formGetUrl + nodeType +
            (nodesToDB.has(topologyNodeId) ? "/" + nodesToDB.get(topologyNodeId).uid : "");

        // get the form of the asset of the type "nodeType" (projects/views.py::get_asset_create_form)
        fetch(getUrl)
        .then(formContent=>formContent.text())
        .then(formContent=> {

            // assign the content of the form to the form tag of the modal
            guiModalDOM.querySelector('.modal-body form').innerHTML = formContent;

            // set parameters which uniquely identify the asset
            guiModalDOM.setAttribute("data-node-type", nodeType);
            guiModalDOM.setAttribute("data-node-topo-id", topologyNodeId);
            guiModalDOM.setAttribute("data-node-df-id", topologyNodeId.split("-").pop());
            editor.editor_mode = "fixed";

            //update the
            ts_data_div = document.getElementById("input_timeseries_data");
            if(ts_data_div){
                var ts_data = JSON.parse(ts_data_div.querySelector("textarea").value);
                var ts_data = ts_data.map(String);
                var ts_idx = [...Array(ts_data.length).keys()];
                ts_idx = ts_idx.map(String);
                makePlotly( ts_idx, ts_data, plot_id="timeseries_trace")
            }



            guiModal.show()
            $('[data-bs-toggle="tooltip"]').tooltip()

        })
        .catch(err => alert("Modal get form JS Error: " + err));

    }
});
// endregion


/* onclick method associated to the save button of the modal */
const submitForm = (e) => {

    // get the parameters which uniquely identify the asset
    const assetTypeName = guiModalDOM.getAttribute("data-node-type");
    const topologyNodeId = guiModalDOM.getAttribute("data-node-topo-id"); // e.g. 'node-2'
    const drawflowNodeId = guiModalDOM.getAttribute("data-node-df-id");

    // rename the node on the fly (to avoid the need of refreshing the page)
    const nodeName = document.getElementById(topologyNodeId).querySelector(".nodeName");
    nodeName.textContent = guiModalDOM.querySelector('input[df-name]').value;

    // get the data of the form
    const assetForm = e.target.closest('.modal-content').querySelector('form');
    const formData = new FormData(assetForm);

    // add the XY position of the node to the form data
    const nodePosX = editor.drawflow.drawflow.Home.data[drawflowNodeId].pos_x
    const nodePosY = editor.drawflow.drawflow.Home.data[drawflowNodeId].pos_y
    formData.set('pos_x', nodePosX);
    formData.set('pos_y', nodePosY);

    // if the asset is a bus, add the input and output ports to the form data
    if (assetTypeName === BUS) {
        const nodeInputs = Object.keys(editor.drawflow.drawflow.Home.data[drawflowNodeId].inputs).length
        const nodeOutputs = Object.keys(editor.drawflow.drawflow.Home.data[drawflowNodeId].outputs).length
        formData.set('input_ports', nodeInputs);
        formData.set('output_ports', nodeOutputs);
    }

    // formPostUrl is defined in scenario_step2.html
    const postUrl = formPostUrl + assetTypeName
        + (nodesToDB.has(topologyNodeId) ? "/" + nodesToDB.get(topologyNodeId).uid : "");

    // send the form of the asset to be saved in database (projects/views.py::asset_create_or_update)
    $.ajax({
        headers: {'X-CSRFToken': csrfToken },
        type: "POST",
        url: postUrl,
        data: formData,
        processData: false,  // tells jQuery not to treat the data
        contentType: false,   // tells jQuery not to define contentType
        success: function (jsonRes) {
            if (jsonRes.success) {
                // add the node id to the nodesToDB mapping
                if (nodesToDB.has(topologyNodeId) === false)
                    nodesToDB.set(topologyNodeId, {uid:jsonRes.asset_id, assetTypeName: assetTypeName });
                guiModal.hide()
            } else {
                assetForm.innerHTML = jsonRes.form_html;
            }

        },
        error: function (err) {
            assetForm.innerHTML = err.responseJSON.form_html;}, //err => {alert("Modal form JS Error: " + err);console.log(err);}
    })
}


/* Triggered before the modal opens */
$("#guiModal").on('show.bs.modal', function (event) {
  var modal = $(event.target)
  // rename the node on the fly (to avoid the need of refreshing the page)
  const nodeName = guiModalDOM.querySelector('input[df-name]').value;
  modal.find('.modal-title').text(nodeName.replaceAll("_", " "));
})

/* Triggered before the modal hides */
$("#guiModal").on('hide.bs.modal', function (event) {
  // reset the modal form to empty
  guiModalDOM.querySelector('.modal-body form').innerHTML = "<form></form>";
  editor.editor_mode = "edit";
})


/* Create node on the gui */
async function createNodeObject(nodeName, connectionInputs = 1, connectionOutputs = 1, nodeData = {}, pos_x, pos_y) {

    // automate the naming of assets to avoid name duplicates
    const editorData = editor.export().drawflow.Home.data;
    const node_list = Object.values(editorData);
    const node_classes = node_list.map(obj => obj.class);
    let existing_items = 0;
    node_classes.map(name => {if(name.includes(nodeName)){++existing_items}});

    let shownName;
    if(typeof nodeData.name === "undefined"){
        if(existing_items == 0){
            shownName = nodeName + "-0"
        }
        else{
            shownName = nodeName + "-" + existing_items
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
