######################################################
### Builtin_defs                                   ###
### Contains definitions for the builtin functions ###
######################################################

builtin_defs = {}

builtin_defs['random'] = '\
.func (.reg .v2 .b32 rval) random ()\n\
{\n\
        .reg .u64 localtmp;\n\
        .reg .f64 localtmp_f;\n\
        .reg .u32 k;\n\
        mul.wide.u32 localtmp, 1664525, %seed.x;\n\
        add.u64 localtmp, localtmp, 1013904223;\n\
        rem.u64 localtmp, localtmp, 4294967296;\n\
        cvt.u32.u64 %seed.x, localtmp;\n\
        cvt.rn.f32.u32 rval.x, %seed.x;\n\
        div.approx.f32 rval.x, rval.x, 4294967295.0;\n\
        mov.u32 rval.y, 2;\n\
        ret;\n\
}\n'

builtin_defs['reduce'] = '\
.func (.reg .v2 .b32 %rval) %lambda (.reg .v2 .b32 x, .reg .v2 .b32 y)\n\
.func (.reg .v2 .b32 rval) reduce (.reg .v2 .b32 list){\n\
        .reg .u32 len;\n\
        .reg .b32 tmp;\n\
        .reg .u32 pos;\n\
        .reg .u32 index;\n\
        .reg .v2 .b32 param<2>;\n\
        .reg .pred run;\n\
        .reg .pred typfloat;\n\
        setp.eq.u32 typfloat, list.y, 3;\n\
@typfloat bra float;\n\
        ld.global.u32 len, [list];\n\
        bra typend;\n\
float:\n\
        ld.global.f32 tmp, [list];\n\
        cvt.rni.u32.f32 len, tmp;\n\
typend:\n\
        add.u32 list.x, list.x, 4;\n\
        mov.u32 pos, 2;\n\
        ld.global.b32 param0.x, [list];\n\
        mov.u32 param0.y, list.y;\n\
        sub.u32 param0.y, param0.y, 2;\n\
        add.u32 list.x, list.x, 4;\n\
        ld.global.b32 param1.x, [list];\n\
        mov.u32 param1.y, list.y;\n\
        sub.u32 param1.y, param1.y, 2;\n\
        add.u32 list.x, list.x, 4;\n\
        call (rval), %lambda, (param0, param1);\n\
start:\n\
        setp.lt.u32 run, pos, len;\n\
  @!run bra end;\n\
        ld.global.b32 param1.x, [list];\n\
        call (rval), %lambda, (rval, param1);\n\
        add.u32 pos, pos, 1;\n\
        add.u32 list.x, list.x, 4;\n\
  @run bra start;\n\
end:\n\
        ret;\n\
}'

#Range is done in Python, therefore the empty PTX string
builtin_defs['range'] = ''
