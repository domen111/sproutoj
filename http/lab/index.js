'use strict'

var console = new function(){
    var that = this;
    var j_con;
    var data = new Array();
    var row = 0,col = 0;

    data[row] = new Array();
    data[row].push('>');

    that.init = function(){
        j_con = $('#console');

        $(window).on('keypress',function(e){
            if(e.which == 13){
                row += 1;    
                data[row] = new Array();
                data[row].push('>');
            }else{
                data[row].push(String.fromCharCode(e.which));
            }
            that.update();
        });
    };

    that.update = function(){
        var i,j;
        var line;

        j_con.empty();

        for(i = 0;i < data.length;i++){
            line = data[i];
            for(j = 0;j < line.length;j++){
                j_con.append(line[j]);
            }
            j_con.append($('<br>'));
        }
    };
}
