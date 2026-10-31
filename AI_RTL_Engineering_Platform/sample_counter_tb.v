module tb_counter4;
    reg clk = 0;
    reg rst_n = 0;
    wire [3:0] count;
    counter4 dut (.clk(clk), .rst_n(rst_n), .count(count));
    always #5 clk = ~clk;
    initial begin
        #12; rst_n = 1;
        repeat (5) begin
            @(posedge clk); #1;
        end
        if (count !== 4'd5) $fatal(1, "FAIL: expected 5, got %0d", count);
        $display("PASS: counter reached 5");
        $finish;
    end
endmodule
