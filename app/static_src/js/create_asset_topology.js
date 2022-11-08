function clearGridModel() {
    Swal.fire({
        title: "Are you sure?",
        text: "This will clear the whole grid model! This will not actually delete any asset from the scenario. You will need to save after clearing for the changes to actually take effect.",
        icon: "warning",
        showCancelButton: true,
        confirmButtonText: "Yes, clear everything!",
        cancelButtonText: "Cancel",
    }).then((result) => result.value && editor.clearModuleSelected());
}

/* Export Topology to JSON and send to back-end. */
$(".btn-export").click(function () {
    // Data Pre-check
    /*
    /* Check if there are duplicate node names in the model
    /* and prevent user from saving the model if there are.
    */
    let editorData = editor.export().drawflow.Home.data;
    const node_list = Object.values(editorData)
    const node_names = node_list.map(obj => obj.data.name);
    const duplicate_names = node_names.filter((name, i, a) => a.indexOf(name) !== i);

    if (duplicate_names.length != 0)
        return Swal.fire('Grid Model Error',
            `There are nodes with duplicate names. \n Rename nodes with names: ${duplicate_names.toString()}`, 'error');
    // End Data Pre-check
    else {
        try {
            const transformIOs = (obj, entry) => {
                const [key, io] = entry;
                obj[key] = io.connections.map(conn =>
                    ("output" in conn) ?
                        ({ node: nodesToDB.get('node-' + conn.node).uid, output: conn.output }) :
                        ({ node: nodesToDB.get('node-' + conn.node).uid, input: conn.input }));
                return obj;
            }

            const drawflowData = Object.values(editorData)
                .map(obj => ({
                    db_id: nodesToDB.get('node-' + obj.id).uid,
                    name: obj.name,
                    inputs: Object.entries(obj.inputs).reduce(transformIOs, {}),
                    outputs: Object.entries(obj.outputs).reduce(transformIOs, {}),
                    data: obj.data,
                    pos_x: obj.pos_x,
                    pos_y: obj.pos_y
                }));

            $.ajax({
                headers: { 'X-CSRFToken': csrfToken },
                type: "POST",
                url: newAssetsCommitTopologyUrl,
                data: JSON.stringify(drawflowData),
                contentType: "application/json; charset=utf-8",
                dataType: "json",
                success: function (resp) {
                    // var node = resp.data;
                    // $.each(node, function (key, val) {
                    //     // add database id to the node data dictionary, in order to discriminate among existing and new nodes.
                    //     editor.drawflow.drawflow.Home.data[`${key}`].data['databaseId'] = val;
                    // });
                    window.location.href = scenarioSearchUrl;
                },
                error: function (XMLHttpRequest, textStatus, errorThrown) {
                    const jsonData = XMLHttpRequest.responseJSON;
                    if (jsonData.specific_obj_type) {
                        Swal.fire('Grid Model Error', `Please fill in all ${jsonData.specific_obj_type.bold()} fields. \n
                   Asset ${jsonData.obj_name.bold()} has empty fields or fields with wrong values.`, 'error');
                        console.log(jsonData.full_error);
                        //console.log(Object.keys(JSON.parse(a.full_error.replaceAll('\'','"'))));
                    } else {
                        Swal.fire('Grid Model Error', `Asset ${jsonData.obj_name.bold()} has empty fields or fields with wrong values.`, 'error');
                    }
                }
            });

        } catch (error) {
            console.error('Error while submiting grid model. ' + error);
            return Swal.fire('Grid Model Error',
                'There are empty assets. \n Make sure all assets are filled in with data.', 'error');
        }

    }
});
