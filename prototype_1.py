''' 80856
ARM 32-bit full binary disassembler using Capstone disassembly framework.
- Daniel Chong
'''
'''
NOTE: CORTEX M processors use THUMB instructions exclusively https://stackoverflow.com/questions/28669905/what-is-the-difference-between-the-arm-thumb-and-thumb-2-instruction-encodings
https://www.keil.com/support/man/docs/armasm/armasm_dom1361289866466.htm
'''
import sys
import struct
from capstone import *
from collections import OrderedDict
import binascii
import math

FILE_NAME = ''
IMAGEBASE = '0x80000'
IS_THUMB_MODE = 1
MAX_INSTR_SIZE = 8
MD = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
REGISTER_NAMES = ['r0', 'r1', 'r2', 'r3', 'r4', 'r5', 'r6', 'r7', 'r8', 'r9'
        , 'r10', 'sl', 'r11', 'r12', 'r13', 'r14', 'r15', 'psr', 'lr', 'pc', 'sp']
BRANCH_INSTRUCTIONS = {'b', 'bl', 'blx', 'bx', 'b.w', 'bl.w', 'blx.w', 'bx.w'}
CONDITIONAL_BRANCHES =  {'blgt', 'blvc', 'blcc', 'blhs', 'blmi', 'blne', 'blal',
        'blle', 'blge', 'blvs',
        'blls', 'bllt', 'bllo', 'blcs', 'blhi', 'bleq', 'blpl', 'bgt', 'bvc', 'bcc',
        'bhs', 'bmi', 'bne', 'bal', 'ble', 'bge', 'bvs', 'bls', 'blt', 'blo', 'bcs',
        'bhi', 'beq', 'bpl', 'bxgt', 'bxvc', 'bxcc', 'bxhs', 'bxmi', 'bxne', 'bxal',
        'bxle', 'bxge', 'bxvs', 'bxls', 'bxlt', 'bxlo', 'bxcs', 'bxhi', 'bxeq', 'bxpl',
        'blxgt', 'blxvc', 'blxcc', 'blxhs', 'blxmi', 'blxne', 'blxal', 'blxle', 'blxge',
        'blxvs', 'blxls', 'blxlt', 'blxlo', 'blxcs', 'blxhi', 'blxeq', 'blxpl',
        'cbz', 'cbnz', 'blgt.w', 'blvc.w', 'blcc.w', 'blhs.w', 'blmi.w', 'blne.w', 'blal.w',
        'blle.w', 'blge.w', 'blvs.w', 'blls.w', 'bllt.w', 'bllo.w', 'blcs.w', 'blhi.w', 'bleq.w',
        'blpl.w', 'bgt.w', 'bvc.w', 'bcc.w', 'bhs.w', 'bmi.w', 'bne.w', 'bal.w', 'ble.w', 'bge.w',
        'bvs.w', 'bls.w', 'blt.w', 'blo.w', 'bcs.w', 'bhi.w', 'beq.w', 'bpl.w', 'bxgt.w', 'bxvc.w',
        'bxcc.w', 'bxhs.w', 'bxmi.w', 'bxne.w', 'bxal.w', 'bxle.w', 'bxge.w', 'bxvs.w', 'bxls.w',
        'bxlt.w', 'bxlo.w', 'bxcs.w', 'bxhi.w', 'bxeq.w', 'bxpl.w', 'blxgt.w', 'blxvc.w', 'blxcc.w',
        'blxhs.w', 'blxmi.w', 'blxne.w', 'blxal.w', 'blxle.w', 'blxge.w', 'blxvs.w', 'blxls.w',
        'blxlt.w', 'blxlo.w', 'blxcs.w', 'blxhi.w', 'blxeq.w', 'blxpl.w', 'cbz.w', 'cbnz.w'}

#Record the location of branch instructions in the binary
BRANCHES = {}
MEM_INSTR = []
STARTING_ADDRESS = ''
HEX_DATA = ''

# Takes a hex representation and returns an int
def endian_switch(val):
    tmp = "0x" + val[6] + val[7] + val[4] + val[5] + val[2] + val[3] + val[0] + val[1]
    return(int(tmp,16))

class instr_data(object):
    def __init__(self, instr, op):
        self.instr = instr
        self.op = op

class DisassemblerCore(object):
    def __init__(self, filename):
        global MEM_INSTR
        global BRANCHES
        self.filename = filename
        self.file_data = b''
        self.starting_address = ''
        self.beginning_code = ''
        self.stack_top = ''
        self.isr_num = 0
        self.isr_table_length = 0
        self.isr_pointers = []
        self.curr_mnemonic = ''
        self.curr_op_str = ''
        self.done = False
        #Keep track of the size of the instruction (can be determined by Capstone)
        self.size = 0
        self.subroutine_branch = []

    def run(self):
        self.load_file()
        for i in range(len(self.file_data)):
            MEM_INSTR.append(0)
        self.disassemble()
        #print('\n\n\nDisassembly\n\n\n')
        disassembled_instrs = 0
        #for i in range(len(MEM_INSTR)):
        #    if MEM_INSTR[i] != 0:
        #        disassembled_instrs += 1
        #        print('%s\t%s'%(hex(i+int(IMAGEBASE,16)), MEM_INSTR[i].instr+' '+MEM_INSTR[i].op))
        #        #if 'b\t#' + hex(i+int(IMAGEBASE,16)) == MEM_INSTR[i]:
        #        #    print'banana'
        #        #    break;
        ##print BRANCHES
        #print('NUMBER OF DISASSEMBLED INSTRUCTIONS:')
        #print(disassembled_instrs)
        return True

    def load_file(self):
        global HEX_DATA, STARTING_ADDRESS
        with open(self.filename, 'rb') as f:
            self.file_data = f.read()
        f.close()
        HEX_DATA = binascii.hexlify(self.file_data)
        # Stack top stored in first word, starting address in second
        self.stack_top = endian_switch(HEX_DATA[0:8])
        self.starting_address = endian_switch(HEX_DATA[8:16])
        STARTING_ADDRESS = self.starting_address
        if self.starting_address % 2 != 0:
            IS_THUMB_MODE = 1
        else:
            IS_THUMB_MODE = 0
        # Detect endianness. (See daniEmu source code documentation if it's open source by now)
        index = 16
        while (True):
            address = endian_switch(HEX_DATA[index:index+8])
            index += 8
            if address != 0:
                if ((address % 2 == 0) or
                        (address > self.starting_address + len(self.file_data)) or
                        (address < self.starting_address - len(self.file_data))):
                    #Weird offset because of "index+=8" and self.beginning_code-thumb_mode
                    self.beginning_code = int(IMAGEBASE,16) + (index-8)/2 + 1
                    print(hex(self.beginning_code))
                    break;
            if(address != 0):
                self.isr_num += 1
            if (address != 0) and (address not in self.isr_pointers):
                self.isr_pointers.append(address)
            self.isr_table_length += 1
        if self.isr_num < 8 or self.starting_address > int("0x40000000", 16):
           print(">>>>BIG ENDIAN DETECTED<<<<")
           index = 16
           del(self.isr_pointers[:])
           self.starting_address = int(HEX_DATA[8:16], 16)
           self.stack_top = int(HEX_DATA[0:8], 16)
           while (True):
               address = int(HEX_DATA[index:index+8], 16)
               index += 8
               if address != 0:
                   if ((address % 2 == 0) or
                           (address > self.starting_address + len(self.file_data)) or
                           (address < self.starting_address - len(self.file_data))):
                       self.beginning_code = address
                       break;
               if (address != 0) and (address not in self.isr_pointers):
                   self.isr_pointers.append(address)
           self.isr_table_length += 1

    #Disassemble ONE instruction
    def dasm_single(self, md, code, addr):
        #Keep track of the number of instructions disassembled

        count = 0
        for(address, size, mnemonic, op_str) in md.disasm_lite(code,
                addr):
            count += 1
            self.curr_mnemonic = str(mnemonic)
            self.curr_op_str = str(op_str)
            instr = self.curr_mnemonic + '\t' + self.curr_op_str
            #MEM_INSTR[address-int(IMAGEBASE,16)] = instr
            MEM_INSTR[address-int(IMAGEBASE,16)] = instr_data(self.curr_mnemonic, self.curr_op_str)
            #if self.curr_mnemonic in self.branch_instructions or self.curr_mnemonic in self.conditional_branches:
            #   BRANCHES[address-int(IMAGEBASE,16)] = str(self.curr_mnemonic) + ', ' + str(self.curr_op_str)
            #debugging
#            print('%s\t%s\t%s\t\t%s'%(hex(address), instr, size, binascii.hexlify(code)))
        '''dasm_single is given 4 bytes. If Capstone is only able to disassemble 1 2-byte instruction,
           the second 2 bytes of the 4 belong to the next instruction.'''
        if count == 1 and size == 2:
            return False
        else:
            return True

    # https://www.capstone-engine.org/lang_python.html
    def disassemble(self):
        start = (self.beginning_code - int(IMAGEBASE, 16) - 1) * 2
        #start = (self.starting_address - int(IMAGEBASE, 16) - 1) * 2
        self.curr_instr = start
        self.curr_addr = self.beginning_code - IS_THUMB_MODE  #offset for thumb
        #self.curr_addr = self.starting_address - IS_THUMB_MODE
        # Section of code to be disassembled
        code = HEX_DATA[self.curr_instr:self.curr_instr+MAX_INSTR_SIZE].decode('hex')
        prev_addr = 0
        while(self.curr_instr+MAX_INSTR_SIZE < len(HEX_DATA)):
            if self.dasm_single(MD, code, self.curr_addr):
                self.curr_instr += MAX_INSTR_SIZE
                self.curr_addr += 4
            else:
                self.curr_instr += MAX_INSTR_SIZE/2
                self.curr_addr += 2
            code = HEX_DATA[self.curr_instr:self.curr_instr+MAX_INSTR_SIZE].decode('hex')


    def toggle_thumb(self):
        if IS_THUMB_MODE == 1:
            IS_THUMB_MODE = 0
            MD = Cs(CS_ARCH_ARM, CS_MODE_ARM)
        elif IS_THUMB_MODE == 0:
            IS_THUMB_MODE = 1
            MD = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

class path_data:
    def __init__(self, path1, path2):
        self.path = path1
        self.branch_path = path2
        self.sources = []
        self.mode = ''
        self.arg = ''

class GeneratorCore(object):
    def __init__(self, disassembly, branches):
        self.mem_instr = disassembly
        self.branches = branches
        self.paths = {}
        self.register_branches = {}
        self.register_branches['r0'] = []
        self.register_branches['r1'] = []
        self.register_branches['r2'] = []
        self.register_branches['r3'] = []
        self.register_branches['r4'] = []
        self.register_branches['r5'] = []
        self.register_branches['r6'] = []
        self.register_branches['r7'] = []
        self.register_branches['r8'] = []
        self.register_branches['r9'] = []
        self.register_branches['r10'] = []
        self.register_branches['r11'] = []
        self.register_branches['r12'] = []
        self.register_branches['r13'] = []
        self.register_branches['r14'] = []
        self.register_branches['r15'] = []
        self.register_branches['lr'] = []
        self.return_address_stack = []
        self.link_reg_branch_dest = 0
        self.link_branch_instructions = {}
        # The beginning of invalid instructions
        self.end = 0
        self.linked_instrs = {}

    def run(self):
        self.generate_paths()
        for i in self.paths:
            print("Address: %s  First Path: %s   Branch Path: %s   Instruction: %s"%(hex(i), hex(self.paths[i].path), hex(self.paths[i].branch_path), self.paths[i].arg))

           #     print("Address: %s  First Path: %s   Branch Path: %s   Instruction: %s"%(hex(i), hex(self.paths[i].path), hex(self.paths[i].branch_path)))

    # Calculate the location of a branch with a register as the argument
    def register_branch_calc(self, instr, op, curr_addr):
        #Calculate branch destinations when argument is a register
        if instr == 'ldr' and 'pc' in op and 'sp' in op:
            return False
        if instr == 'ldr' and 'pc' in op:
            addr = curr_addr + int(IMAGEBASE, 16)
            reg = op.split(',')[0]
            arg = op.split('#')[1]
            arg = int(arg[:-1],16)
            loc = int(math.floor((addr + arg)/4)*4)
            # 8 for doubleword offset
            loc = int(loc - int(IMAGEBASE, 16)) * 2 + 8
            data = HEX_DATA[loc:loc+8]
            reg_br_addr = endian_switch(data)-1
            self.register_branches[reg].append(reg_br_addr)
            return True
        else:
            return False

    # Link subroutine paths
    def subroutine_linking(self, instr, op, curr_addr):
        global BRANCH_INSTRUCTIONS, REGISTER_NAMES, CONDITIONAL_BRANCHES, MEM_INSTR
        if instr in BRANCH_INSTRUCTIONS:
            if 'bl' in instr:
                self.depth += 1
                index = curr_addr + 1
                while(MEM_INSTR[index] == 0):
                    index += 1
                index += int(IMAGEBASE,16)
                if op in REGISTER_NAMES:
                    print 'nonconditional bl'
                    self.return_address_stack.append(index-int(IMAGEBASE,16))
                    dest = self.register_branches[op].pop()
                    self.paths[curr_addr+int(IMAGEBASE,16)] = path_data(0, dest)
                    self.paths[curr_addr+int(IMAGEBASE,16)].arg = instr + ' ' + op
                    self.link_reg_branch_dest = dest-int(IMAGEBASE,16)
                    print self.link_reg_branch_dest
                    print instr + op
                    print hex(self.link_reg_branch_dest+int(IMAGEBASE,16))
                    print hex(curr_addr+int(IMAGEBASE,16))
                else:
                    self.return_address_stack.append(index-int(IMAGEBASE,16))
                    dest = int(op.split('#')[1],16)
                    self.paths[curr_addr+int(IMAGEBASE,16)] = path_data(0, dest)
                    self.paths[curr_addr+int(IMAGEBASE,16)].arg = instr + ' ' + op
                    self.link_reg_branch_dest = dest-int(IMAGEBASE,16)
                return 1
        elif instr in CONDITIONAL_BRANCHES:
            if 'bl' in instr:
                self.depth += 1
                index = curr_addr + 1
                while(MEM_INSTR[index] == 0):
                    index += 1
                index += int(IMAGEBASE,16)
                if op in REGISTER_NAMES:
                    print 'conditional bl'
                    self.return_address_stack.append(index-int(IMAGEBASE,16))
                    dest = self.register_branches[op].pop()
                    #self.return_address_stack.append(dest-int(IMAGEBASE,16))  INCORRECT
                    self.paths[curr_addr+int(IMAGEBASE,16)] = path_data(index, dest)
                    self.paths[curr_addr+int(IMAGEBASE,16)].arg = instr + ' ' + op
                    self.link_reg_branch_dest = dest-int(IMAGEBASE,16)
                else:
                    self.return_address_stack.append(index-int(IMAGEBASE,16))
                    dest = int(op.split('#')[1],16)
                    self.paths[curr_addr+int(IMAGEBASE,16)] = path_data(index, dest)
                    self.paths[curr_addr+int(IMAGEBASE,16)].arg = instr + ' ' + op
                return 1
        if instr in BRANCH_INSTRUCTIONS and 'bl' not in instr and self.depth != 0:
            #print hex(curr_addr+int(IMAGEBASE,16)), instr, op
            if op in REGISTER_NAMES:
                dest = self.register_branches[op].pop()
            else:
                dest = int(op.split('#')[1],16)
            self.link_reg_branch_dest = dest-int(IMAGEBASE,16)

            if op == 'lr':
                if instr == 'pop' or instr in BRANCH_INSTRUCTIONS or instr in CONDITIONAL_BRANCHES:
                    print 'poop'
                return 1
        return 0

    # Find all branch with link instructions
    def link_detection(self, mem_instr, starting_address):
        global BRANCH_INSTRUCTIONS, CONDITIONAL_BRANCHES, IS_THUMB_MODE
        i = starting_address-int(IMAGEBASE,16)-IS_THUMB_MODE
        while i < len(mem_instr)-1:
            if mem_instr[i] != 0:
                instr = mem_instr[i].instr
                if instr in BRANCH_INSTRUCTIONS or instr in CONDITIONAL_BRANCHES:
                    if 'bl' in instr:
                        self.link_branch_instructions[i] = True
            i += 1

    def link_subroutines(self, bl_addrs, mem_instr):
        for i in bl_addrs:
            index = i
            instr = mem_instr[i].instr
            op = mem_instr[i].op
            dest = 0
            if op in REGISTER_NAMES:
                # examine previous memory addresses until corresponding load instruction is found
                while len(self.register_branches[op]) == 0:
                    self.register_branch_calc(mem_instr[index].instr, mem_instr[index].op, index)
                    index -= 1
                    while mem_instr[index] == 0:
                        index -= 1
                dest = self.register_branches[op].pop()
            else:
                dest = int(op.split('#')[1],16)

            if instr in BRANCH_INSTRUCTIONS:
                self.paths[i+int(IMAGEBASE,16)] = path_data(0, dest)
            else:
                index = i + 1
                while(mem_instr[index] == 0):
                    index += 1
                index += int(IMAGEBASE,16)
                self.paths[i+int(IMAGEBASE,16)] = path_data(index, dest)

    def branch_with_link_handler(self, addr):
        global MEM_INSTR
        try:
            while(MEM_INSTR[addr] == 0):
                addr += 1
            instr = MEM_INSTR[addr].instr
            op = MEM_INSTR[addr].op
            #return to return address
            if ('pop' in instr and 'pc' in op) or ('ldr' in instr and 'pc' in op and 'sp' in op):
                ret_addr = self.return_address_stack.pop()
                self.paths[addr+int(IMAGEBASE,16)] = path_data(0, ret_addr)
                self.paths[addr+int(IMAGEBASE,16)].arg = instr + ' ' + op
                print(hex(addr+int(IMAGEBASE,16)), 'poppity', hex(ret_addr))
                return
            elif (instr in BRANCH_INSTRUCTIONS or instr in CONDITIONAL_BRANCHES) and 'lr' in op:
                ret_addr = self.return_address_stack.pop()
                self.paths[addr+int(IMAGEBASE,16)] = path_data(0, ret_addr)
                self.paths[addr+int(IMAGEBASE,16)].arg = instr + ' ' + op
                print(hex(addr+int(IMAGEBASE,16)), 'ldrin', hex(ret_addr))
                return
            else:
                if 'bl' in instr:
                    self.register_branch_calc(instr, op, addr)
                    b_result = self.branch_destination_handler(instr, op, addr)
                    if b_result[0] == True:
                        self.linked_instrs[addr] = True
                        self.paths[addr+int(IMAGEBASE,16)] = path_data(b_result[1], b_result[2])
                        self.paths[addr+int(IMAGEBASE,16)].arg = instr + ' ' + op
                        index = addr + 1
                        while(MEM_INSTR[index] == 0):
                            index += 1
                        index += int(IMAGEBASE,16)
                        self.return_address_stack.append(index)
                        self.branch_with_link_handler(b_result[2]-int(IMAGEBASE,16))
                else:
                    self.register_branch_calc(instr, op, addr)
                    self.branch_with_link_handler(addr+1)
        except:
            print 'CANNOT CONTINUE'
            return

    #Return format: branch instruction?, first branch path, second path, next instruction to handle
    def branch_destination_handler(self, instr, op, addr):
        global MEM_INSTR
        if instr in BRANCH_INSTRUCTIONS:
            dest = 0
            if op in REGISTER_NAMES:
                dest = self.register_branches[op].pop()
            else:
                dest = int(op.split('#')[1],16)
            return (True, 0, dest, addr + 1)
        elif instr in CONDITIONAL_BRANCHES:
            index = addr + 1
            while(MEM_INSTR[index] == 0):
                index += 1
            index += int(IMAGEBASE,16)
            dest = 0
            if op in REGISTER_NAMES:
                dest = self.register_branches[op].pop()
            else:
                dest = int(op.split('#')[1],16)
            return (True, index, dest, addr + 1)
        else:
            return (False, 0, 0, 0)

    # Link all other instructions
    def instruction_linking(self, start):
        global BRANCH_INSTRUCTIONS, REGISTER_NAMES, CONDITIONAL_BRANCHES
        i = start
        while i < len(MEM_INSTR)-1:
            if MEM_INSTR[i] != 0:
                instr = MEM_INSTR[i].instr
                op = MEM_INSTR[i].op
                #print hex(i+int(IMAGEBASE,16)), instr, op
                self.register_branch_calc(instr, op, i)

                #instructions that will be handled by the link instruction functions
                if 'bl' in instr and i not in self.linked_instrs:
                    self.branch_with_link_handler(i)
                    i += 1
                elif instr in BRANCH_INSTRUCTIONS and op == 'lr':
                    i += 1
                elif instr in CONDITIONAL_BRANCHES and op == 'lr':
                    i += 1
                elif 'pop' in instr:
                    i += 1
                
                else:
                    try:
                        b_result = self.branch_destination_handler(instr, op, i)
                        if b_result[0] == True:
                            self.paths[i+int(IMAGEBASE,16)] = path_data(b_result[1], b_result[2])
                            self.paths[i+int(IMAGEBASE,16)].arg = instr + ' ' + op
                            i = b_result[3]
                        else:
                            index = i + 1
                            while(MEM_INSTR[index] == 0):
                                index += 1
                            index += int(IMAGEBASE,16)
                            self.paths[i+int(IMAGEBASE,16)] = path_data(index, 0)
                            self.paths[i+int(IMAGEBASE,16)].arg = instr + ' ' + op
                            i += 1
                    except:
                        self.paths[i+int(IMAGEBASE,16)] = path_data(0, 0)
                        self.paths[i+int(IMAGEBASE,16)].arg = instr + ' ' + op
                        i += 1
            else:
                i += 1



    def generate_paths(self):
        '''mem_instr and branches have the imagebase subtracted from them!!'''
        global STARTING_ADDRESS, MEM_INSTR, BRANCHES, BRANCH_INSTRUCTIONS, CONDITIONAL_BRANCHES, HEX_DATA, IS_THUMB_MODE

        i = STARTING_ADDRESS-int(IMAGEBASE,16)-IS_THUMB_MODE

        self.link_detection(MEM_INSTR, STARTING_ADDRESS)
        self.instruction_linking(i)
        #for address in self.link_branch_instructions:
        #    print(hex(address+int(IMAGEBASE,16)), MEM_INSTR[address].instr, MEM_INSTR[address].op)
        #    #print hex(i+int(IMAGEBASE,16))
        #self.link_subroutines(self.link_branch_instructions, MEM_INSTR)

        #while i < range(len(MEM_INSTR)):
        #    if MEM_INSTR[i] != 0:

        #        instr = MEM_INSTR[i].instr
        #        op = MEM_INSTR[i].op
        #        self.register_branch_calc(instr, op, i)

        #        if instr in BRANCH_INSTRUCTIONS:
        #            if 'bl' in instr:
        #                self.register_branches['lr'].append(i+int(IMAGEBASE,16)+2)

        #            if op in REGISTER_NAMES:
        #                self.paths[i+int(IMAGEBASE,16)] = path_data(0, self.register_branches[op].pop())
        #                self.paths[i+int(IMAGEBASE,16)].arg = instr + ' ' + op
        #                if op == 'lr':
        #                    print instr + op
        #                    break;
        #            else:
        #                self.paths[i+int(IMAGEBASE,16)] = path_data(0, int(op.split('#')[1],16))
        #                self.paths[i+int(IMAGEBASE,16)].arg = instr + ' ' + op

        #        elif instr in CONDITIONAL_BRANCHES:
        #            if 'bl' in instr:
        #                self.register_branches['lr'].append(i+int(IMAGEBASE,16)+2)
        #            index = i + 1
        #            while(MEM_INSTR[index] == 0):
        #                index += 1
        #            index += int(IMAGEBASE,16)
        #            if op in REGISTER_NAMES:
        #                self.paths[i+int(IMAGEBASE,16)] = path_data(index, self.register_branches[op].pop())
        #                self.paths[i+int(IMAGEBASE,16)].arg = instr + ' ' + op
        #                if op == 'lr':
        #                    print instr + op
        #                    break;
        #            else:
        #                self.paths[i+int(IMAGEBASE,16)] = path_data(index, int(op.split('#')[1],16))
        #                self.paths[i+int(IMAGEBASE,16)].arg = instr + ' ' + op

        #        else:
        #            index = i + 1
        #            while(MEM_INSTR[index] == 0):
        #                index += 1
        #            index += int(IMAGEBASE,16)
        #            self.paths[i+int(IMAGEBASE,16)] = path_data(index, 0)
        #            self.paths[i+int(IMAGEBASE,16)].arg = instr + ' ' + op
        #    i += 1
        #if len(self.paths[STARTING_ADDRESS-int(IMAGEBASE,16)-IS_THUMB_MODE].sources) == 0:
        #    self.paths[STARTING_ADDRESS-int(IMAGEBASE,16)-IS_THUMB_MODE].sources.append(0)
        return 0

# Main
def main():
    tmp = False
    if len(sys.argv) > 1:
        FILE_NAME = str(sys.argv[1])
        #IMAGEBASE = str(sys.argv[2])
        with open('startup.txt', 'w') as f:
            f.write(FILE_NAME)
            #f.write(IMAGEBASE)
            f.close()
    else:
        with open('startup.txt', 'r') as f:
            FILE_NAME = f.readline()
            f.close()
        if len(FILE_NAME) == 0:
            print('No file found')
            return True
    dc = DisassemblerCore(FILE_NAME)
    dc.run()
    gc = GeneratorCore(MEM_INSTR, BRANCHES)
    gc.run()

if __name__ == '__main__':
    main()
