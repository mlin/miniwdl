import unittest, inspect
from .context import WDL

class TestEval(unittest.TestCase):

    def test_boolean(self):
        expr = WDL.parse_expr("true")
        expr.infer_type(WDL.Expr.TypeEnv())
        self.assertIsInstance(expr.type, WDL.Type.Boolean)
        self.assertEqual(str(expr.type), "Boolean")
        val = expr.eval(WDL.Expr.Env())
        self.assertIsInstance(val, WDL.Value.Boolean)
        self.assertEqual(str(val.type), "Boolean")
        self.assertEqual(val.value, True)
        self.assertEqual(str(val), "true")
        self.assertEqual(val, WDL.Value.Boolean(True))
        self.assertNotEqual(val, WDL.Value.Boolean(False))

        expr = WDL.parse_expr("false")
        expr.infer_type(WDL.Expr.TypeEnv())
        self.assertEqual(str(expr.type), "Boolean")
        val = expr.eval(WDL.Expr.Env())
        self.assertEqual(str(val.type), "Boolean")
        self.assertEqual(val.value, False)
        self.assertEqual(str(val), "false")
        self.assertEqual(val, WDL.Value.Boolean(False))
        self.assertNotEqual(val, WDL.Value.Boolean(True))

    def _test_tuples(self, *tuples):
        for tuple in tuples:
            assert(len(tuple) >= 2)
            expr = tuple[0]
            expected = tuple[1]
            env = None
            expected_type = None
            exn = None
            for x in tuple[2:]:
                if isinstance(x, WDL.Expr.Env):
                    env = x
                elif isinstance(x, WDL.Expr.TypeEnv):
                    type_env = x
                elif isinstance(x, WDL.Type.Base):
                    expected_type = x
                elif inspect.isclass(x):
                    exn = x
                else:
                    assert False
            type_env = WDL.Expr.TypeEnv()
            if env is not None:
                env_walker = env
                while env_walker is not None:
                    if env_walker.binding is not None:
                        type_env = WDL.Expr.TypeEnv((env_walker.binding[0], env_walker.binding[1].type), type_env)
                    env_walker = env_walker.parent
            if exn:
                with self.assertRaises(exn, msg=expected):
                    x = WDL.parse_expr(expr).infer_type(type_env).eval(env)
            else:
                v = WDL.parse_expr(expr).infer_type(type_env).eval(env).expect(expected_type)
                self.assertEqual(str(v), expected)

    def test_logic(self):
        self._test_tuples(
            ("true && true", "true", WDL.Type.Boolean()),
            ("true && false", "false"),
            ("false && true", "false"),
            ("false && false", "false"),
            ("true || true", "true"),
            ("true || false", "true"),
            ("false || true", "true"),
            ("false || false", "false"),
            ("false && true || true && true", "true"),
            ("true && !false || false", "true"),
            ("!true", "false"),
            ("!!true", "true"),
            ("!false", "true"),
            ("!false && true", "true"),
            ("!(false && true)", "true")
        )

    def test_arithmetic(self):
        self._test_tuples(
            ("1", "1"),
            ("-1","-1"),
            ("0-1","-1"),
            ("1+1", "2"),
            ("2*3+4","10"),
            ("2*(3+4)","14"),
            ("2+3*4","14"),
            ("1+6/3*4","9"),
            ("1-4/3","0"),
            ("1--4/3","3"), # -4/3 == -2, is this right?
            ("4%2","0"),
            ("4%3","1"),
            ("1 + false", "(Ln 1, Col 1) Non-numeric operand to + operator", WDL.Error.IncompatibleOperand)
        )

    def test_cmp(self):
        self._test_tuples(
            ("1 == 1","true"),
            ("1 == 0","false"),
            ("1 != 1","false"),
            ("1 != 0","true"),
            ("1 < 1","false"),
            ("1 <= 1","true"),
            ("1<2","true"),
            ("1<=2","true"),
            ("1>1","false"),
            ("1>=1","true"),
            ("1>2","false"),
            ("1>=0","true"),
            ("3<2 || 1>=0","true"),
            ("3<2&&1>=0","false"),
            ("3<2&&1>=0||1==1","true"),
            ("1 == false", "(Ln 1, Col 1) Cannot compare Int and Boolean", WDL.Error.IncompatibleOperand)
        )

    def test_str(self):
        self._test_tuples(
            ('"true"', '"true"', WDL.Type.String()),
            ('"true" == "true"', 'true', WDL.Type.Boolean()),
            ('"true" != "true"', 'false', WDL.Type.Boolean()),
            ('"true" == "foo"', 'false', WDL.Type.Boolean()),
            ('"true" != "bar"', 'true', WDL.Type.Boolean()),
            ('"foo" + "bar"', '"foobar"'),
            ('"foo" + 1', '"foo1"'),
            ('2.0 + "bar"', '"2.0bar"'),
            (""" 'foo' + "bar" """, '"foobar"'))
        self._test_tuples(
            (r'''"CNN is working frantically to find their \"source.\""''',
             r'''"CNN is working frantically to find their \"source.\""'''),
            (r"""'CNN is working frantically to find their "source."'""",
             r'''"CNN is working frantically to find their \"source.\""'''),
            (r"""'The fact is that many anonymous sources don\'t even exist.'""",
             r'''"The fact is that many anonymous sources don't even exist."''')
        )

    def test_if(self):
        self._test_tuples(
            ("if false then 0 else 1","1", WDL.Type.Int()),
            ("if true then 0 else 1","0"),
            ("if false then 0 else 1+2","3"),
            ("(if false then 0 else 1)+2","3"),
            ("(if 1>0 then 1+1 else 1)+1","3"),
            ("if 1>0 then if true then 1 else 2 else 3","1"),            
            ("if 3.14 then 0 else 1", "(Ln 1, Col 1) Expected Boolean instead of Float; in if condition", WDL.Error.StaticTypeMismatch),
            ("if 0 < 1 then 0 else false", "(Ln 1, Col 1) Expected Int instead of Boolean; if consequent & alternative must have the same type", WDL.Error.StaticTypeMismatch),
            ("if true then 1 else 2.0", "1.0", WDL.Type.Float()),
            ("if false then 1 else 2.0", "2.0", WDL.Type.Float()),
            ("if true then 1.0 else 2", "1.0", WDL.Type.Float()),
            ("if false then 1.0 else 2", "2.0", WDL.Type.Float())
        )

    def test_array(self):
        expr = WDL.parse_expr("[true,false]")
        expr.infer_type(WDL.Expr.TypeEnv())
        self.assertEqual(str(expr.type), "Array[Boolean]")

        env = WDL.Expr.Env()
        val = expr.eval(env)
        self.assertIsInstance(val, WDL.Value.Array)
        self.assertEqual(str(val.type), "Array[Boolean]")
        self.assertEqual(str(val), "[true, false]")

        self._test_tuples(
            ("[true, false][0]", "true"),
            ("[true, false][1]", "false"),
            ("[1+2, 3*4][1]", "12"),
            ("[]","[]", WDL.Type.Array(None)),
            ("[] == []","true"),
            ("[1, false]", "(Ln 1, Col 1) Expected Int instead of Boolean; inconsistent types within array", WDL.Error.StaticTypeMismatch),
            ("1 + 2[3]", "(Ln 1, Col 5) Not an array", WDL.Error.NotAnArray),
            ("[1, 2, 3][true]", "(Ln 1, Col 11) Expected Int instead of Boolean; Array index", WDL.Error.StaticTypeMismatch),
            ("[1, 2, 3][4]", "(Ln 1, Col 11) Array index out of bounds", WDL.Error.OutOfBounds)
        )

    def test_float_coercion(self):
        self._test_tuples(
            ("1 + 1.0", "2.0", WDL.Type.Float()),
            ("1.0 + 1", "2.0", WDL.Type.Float()),
            ("1 == 1.0", "true"),
            ("1 == 1.1", "false"),
            ("1 != 1.1", "true"),
            ("1 < 1.0", "false"),
            ("1 <= 1.0", "true"),
            ("[1, 2.0]", "[1.0, 2.0]", WDL.Type.Array(WDL.Type.Float())),
            ("[1, 2.0][0]", "1.0", WDL.Type.Float())
        )

    def test_ident(self):
        env = cons_env(("pi", WDL.Value.Float(3.14159)), ("e", WDL.Value.Float(2.71828)),
                        ("t", WDL.Value.Boolean(True)), ("f", WDL.Value.Boolean(False)))
        self._test_tuples(
            ("pi", "3.14159", WDL.Type.Float(), env),
            ("bogus", "(Ln 1, Col 1) Unknown identifier", WDL.Error.UnknownIdentifier, env),
            ("pi+e", "5.85987", env),
            ("t||f", "true", WDL.Type.Boolean(), env),
            ("if t then pi else e", "3.14159", env),
        )


    def test_interpolation(self):
        env = cons_env(("pi", WDL.Value.Float(3.14159)), ("e", WDL.Value.Float(2.71828)),
                        ("t", WDL.Value.Boolean(True)), ("f", WDL.Value.Boolean(False)))
        self._test_tuples(
            ('"${pi}"', '"3.14159"', env),
            ('"pi = ${pi}!"', '"pi = 3.14159!"', env),
            ('"pi+e = ${pi+e}!"', '"pi+e = 5.85987!"', env),
            ("'This is ${t}'", '"This is true"', env),
            ("'${f} is ${f}'", '"false is false"', env),
            ('"$"','"$"'),
            ('"$shell"','"$shell"'),
            ("'c$'",'"c$"'),
            ("'The U.$. is re$pected again!'",'"The U.$. is re$pected again!"')
        )

    def test_errors(self):
        self._test_tuples(
            ("1 + bogus(2)", "(Ln 1, Col 5) No such function: bogus", WDL.Error.NoSuchFunction)
        )

def cons_env(*bindings):
    env = WDL.Expr.Env()
    for p in bindings:
        env = WDL.Expr.Env(p, env)
    return env
