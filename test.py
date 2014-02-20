#!/usr/bin/env python

import nose
import logging
l = logging.getLogger("simuvex.test")

try:
	# pylint: disable=W0611
	import standard_logging
	import angr_debug
except ImportError:
	pass

import symexec as se
from simuvex import SimMemory, Vectorizer
from simuvex import SimValue, ConcretizingException, SimState
from simuvex import s_ccall, SimProcedures

# pylint: disable=R0904
def test_memory():
	initial_memory = { 0: 'A', 1: 'A', 2: 'A', 3: 'A', 10: 'B' }
	vectorized_memory = Vectorizer(initial_memory)
	mem = SimMemory(backer=vectorized_memory)

	# concrete address and concrete result
	loaded_val = SimValue(mem.load(0, 4)[0]) # Returns: a z3 BitVec representing 0x41414141
	nose.tools.assert_false(loaded_val.is_symbolic())
	nose.tools.assert_equal(loaded_val.any(), 0x41414141)

	# concrete address and partially symbolic result
	loaded_val = SimValue(mem.load(2, 4)[0])
	nose.tools.assert_true(loaded_val.is_symbolic())
	nose.tools.assert_false(loaded_val.is_unique())
	nose.tools.assert_greater_equal(loaded_val.any(), 0x41410000)
	nose.tools.assert_less_equal(loaded_val.any(), 0x41420000)
	nose.tools.assert_equal(loaded_val.min(), 0x41410000)
	nose.tools.assert_equal(loaded_val.max(), 0x4141ffff)

	# symbolic (but fixed) address and concrete result
	x = se.BitVec('x', 64)
	addr = SimValue(x, constraints = [ x == 10 ])
	loaded_val = SimValue(mem.load(addr, 1)[0])
	nose.tools.assert_false(loaded_val.is_symbolic())
	nose.tools.assert_equal(loaded_val.any(), 0x42)

def test_symvalue():
	# concrete symvalue
	zero = SimValue(se.BitVecVal(0, 64))
	nose.tools.assert_false(zero.is_symbolic())
	nose.tools.assert_equal(zero.any(), 0)
	nose.tools.assert_raises(ConcretizingException, zero.exactly_n, 2)

	# symbolic symvalue
	x = se.BitVec('x', 64)
	sym = SimValue(x, constraints = [ x > 100, x < 200 ])
	nose.tools.assert_true(sym.is_symbolic())
	nose.tools.assert_equal(sym.min(), 101)
	nose.tools.assert_equal(sym.max(), 199)
	nose.tools.assert_items_equal(sym.any_n(99), range(101, 200))
	nose.tools.assert_raises(ConcretizingException, zero.exactly_n, 102)

def test_state_merge():
	a = SimState()
	a.store_mem(1, se.BitVecVal(42, 8))

	b = a.copy_exact()
	c = b.copy_exact()
	a.store_mem(2, a.mem_expr(1, 1)+1)
	b.store_mem(2, b.mem_expr(1, 1)*2)
	c.store_mem(2, c.mem_expr(1, 1)/2)

	# make sure the byte at 1 is right
	nose.tools.assert_equal(a.mem_value(1, 1).any(), 42)
	nose.tools.assert_equal(b.mem_value(1, 1).any(), 42)
	nose.tools.assert_equal(c.mem_value(1, 1).any(), 42)

	# make sure the byte at 2 is right
	nose.tools.assert_equal(a.mem_value(2, 1).any(), 43)
	nose.tools.assert_equal(b.mem_value(2, 1).any(), 84)
	nose.tools.assert_equal(c.mem_value(2, 1).any(), 21)

	# the byte at 2 should be unique for all before the merge
	nose.tools.assert_true(a.mem_value(2, 1).is_unique())
	nose.tools.assert_true(b.mem_value(2, 1).is_unique())
	nose.tools.assert_true(c.mem_value(2, 1).is_unique())

	merge_val = a.merge(b, c)

	# the byte at 2 should now *not* be unique for a
	nose.tools.assert_false(a.mem_value(2, 1).is_unique())
	nose.tools.assert_true(b.mem_value(2, 1).is_unique())
	nose.tools.assert_true(c.mem_value(2, 1).is_unique())

	# the byte at 2 should have the three values
	nose.tools.assert_items_equal(a.mem_value(2, 1).any_n(10), (43, 84, 21))

	# we should be able to select them by adding constraints
	a_a = a.copy_exact()
	a_a.add_constraints(merge_val == 0)
	nose.tools.assert_true(a_a.mem_value(2, 1).is_unique())
	nose.tools.assert_equal(a_a.mem_value(2, 1).any(), 43)

	a_b = a.copy_exact()
	a_b.add_constraints(merge_val == 1)
	nose.tools.assert_true(a_b.mem_value(2, 1).is_unique())
	nose.tools.assert_equal(a_b.mem_value(2, 1).any(), 84)

	a_c = a.copy_exact()
	a_c.add_constraints(merge_val == 2)
	nose.tools.assert_true(a_c.mem_value(2, 1).is_unique())
	nose.tools.assert_equal(a_c.mem_value(2, 1).any(), 21)

def test_ccall():
	l.debug("Testing amd64_actions_ADD")
	l.debug("(8-bit) 1 + 1...")
	arg_l = se.BitVecVal(1, 8)
	arg_r = se.BitVecVal(1, 8)
	ret = s_ccall.amd64_actions_ADD(8, arg_l, arg_r, 0)
	nose.tools.assert_equal(ret, 0)

	l.debug("(32-bit) (-1) + (-2)...")
	arg_l = se.BitVecVal(-1, 32)
	arg_r = se.BitVecVal(-1, 32)
	ret = s_ccall.amd64_actions_ADD(32, arg_l, arg_r, 0)
	nose.tools.assert_equal(ret, 0b101010)

	l.debug("Testing amd64_actions_SUB")
	l.debug("(8-bit) 1 - 1...",)
	arg_l = se.BitVecVal(1, 8)
	arg_r = se.BitVecVal(1, 8)
	ret = s_ccall.amd64_actions_SUB(8, arg_l, arg_r, 0)
	nose.tools.assert_equal(ret, 0b010100)

	l.debug("(32-bit) (-1) - (-2)...")
	arg_l = se.BitVecVal(-1, 32)
	arg_r = se.BitVecVal(-1, 32)
	ret = s_ccall.amd64_actions_SUB(32, arg_l, arg_r, 0)
	nose.tools.assert_equal(ret, 0)

def test_inline_strlen():
	s = SimState(arch="AMD64", mode="symbolic")

	l.info("fully concrete string")
	a_str = se.BitVecVal(0x41414100, 32)
	a_addr = se.BitVecVal(0x10, 64)
	s.store_mem(a_addr, a_str, endness="Iend_BE")
	a_len = SimProcedures['libc.so.6']['strlen'](s, inline=True, arguments=[a_addr]).ret_expr
	nose.tools.assert_true(s.expr_value(a_len).is_unique())
	nose.tools.assert_equal(s.expr_value(a_len).any(), 3)

	l.info("concrete-terminated string")
	b_str = se.Concat(se.BitVec("mystring", 24), se.BitVecVal(0, 8))
	b_addr = se.BitVecVal(0x20, 64)
	s.store_mem(b_addr, b_str, endness="Iend_BE")
	b_len = SimProcedures['libc.so.6']['strlen'](s, inline=True, arguments=[b_addr]).ret_expr
	nose.tools.assert_equal(s.expr_value(b_len).max(), 3)
	nose.tools.assert_items_equal(s.expr_value(b_len).any_n(10), (0,1,2,3))

	l.info("fully unconstrained")
	u_addr = se.BitVecVal(0x50, 64)
	u_len = SimProcedures['libc.so.6']['strlen'](s, inline=True, arguments=[u_addr]).ret_expr
	nose.tools.assert_equal(len(s.expr_value(u_len).any_n(100)), 16)
	nose.tools.assert_equal(s.expr_value(u_len).max(), 15)

	#
	# This tests if a strlen can influence a symbolic str.
	#
	l.info("Trying to influence length.")
	s = SimState(arch="AMD64", mode="symbolic")
	str_c = se.BitVec("some_string", 8*16)
	c_addr = se.BitVecVal(0x10, 64)
	s.store_mem(c_addr, str_c, endness='Iend_BE')
	c_len = SimProcedures['libc.so.6']['strlen'](s, inline=True, arguments=[c_addr]).ret_expr
	nose.tools.assert_equal(len(s.expr_value(c_len).any_n(100)), 16)
	nose.tools.assert_equal(s.expr_value(c_len).max(), 15)

	one_s = s.copy_after()
	one_s.add_constraints(c_len == 1)
	nose.tools.assert_equal(one_s.expr_value(str_c).any_str().index('\x00'), 1)
	str_test = one_s.mem_value(c_addr, 2, endness='Iend_BE')
	nose.tools.assert_equal(len(str_test.any_n_str(300)), 255)

	for i in range(2):
		test_s = s.copy_after()
		test_s.add_constraints(c_len == i)
		str_test = test_s.mem_value(c_addr, i + 1, endness='Iend_BE')
		nose.tools.assert_equal(str_test.any_str().index('\x00'), i)
		nose.tools.assert_equal(len(str_test.any_n_str(2 ** (i*8) + 1)), 2 ** (i*8) - i)

def test_inline_strcmp():
	s = SimState(arch="AMD64", mode="symbolic")
	str_a = se.BitVecVal(0x41414100, 32)
	str_b = se.BitVec("mystring", 32)

	a_addr = se.BitVecVal(0x10, 64)
	b_addr = se.BitVecVal(0xb0, 64)

	s.store_mem(a_addr, str_a)
	s.store_mem(b_addr, str_b)

	s_cmp = s.copy_after()
	cmpres = SimProcedures['libc.so.6']['strcmp'](s_cmp, inline=True, arguments=[a_addr, b_addr]).ret_expr
	s_match = s_cmp.copy_after()
	s_nomatch = s_cmp.copy_after()
	s_match.add_constraints(cmpres == 0)
	s_nomatch.add_constraints(cmpres != 0)

	nose.tools.assert_true(s_match.expr_value(str_b).is_unique())
	nose.tools.assert_false(s_nomatch.expr_value(str_b).is_unique())
	nose.tools.assert_equal(s_match.expr_value(str_b).any_str(), "AAA\x00")

	s_ncmp = s.copy_after()
	ncmpres = SimProcedures['libc.so.6']['strncmp'](s_ncmp, inline=True, arguments=[a_addr, b_addr, se.BitVecVal(2, s.arch.bits)]).ret_expr
	s_match = s_ncmp.copy_after()
	s_nomatch = s_ncmp.copy_after()
	s_match.add_constraints(ncmpres == 0)
	s_nomatch.add_constraints(ncmpres != 0)

	nose.tools.assert_false(s_match.expr_value(str_b).is_unique())
	nose.tools.assert_true(s_match.mem_value(b_addr, 2).is_unique())
	nose.tools.assert_equal(len(s_match.mem_value(b_addr, 3).any_n(300)), 256)
	nose.tools.assert_false(s_nomatch.expr_value(str_b).is_unique())

if __name__ == '__main__':
	test_inline_strcmp()
