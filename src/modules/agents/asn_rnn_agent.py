import torch as th
import torch.nn as nn
import torch.nn.functional as F


class AsnRNNAgent(nn.Module):
    def __init__(self, input_shape, args):
        super(AsnRNNAgent, self).__init__()
        self.args = args

        # feature index
        self.move_feat_end = args.move_feats_size

        self.blood_feat_start = args.move_feats_size + args.enemy_feats_size * self.args.enemies_num + args.agent_feats_size * (self.args.agents_num - 1)
        # self.blood_feat_start = 5 + 5 * 8 + 5 * 8
        self.blood_feat_end = self.blood_feat_start + 1

        self.other_feat_start = args.move_feats_size + args.enemy_feats_size * self.args.enemies_num + args.agent_feats_size * (self.args.agents_num - 1) + 1
        # self.other_feat_start = 5 + 5 * 8 + 5 * 8 + 1

        self.enemies_feat_start = args.move_feats_size

        self.agents_feat_start = args.move_feats_size + args.enemy_feats_size * self.args.enemies_num


        # network struct
        self.env_info_fc1 = nn.Linear(input_shape, args.asn_hidden_size)
        self.env_info_fc2 = nn.Linear(args.asn_hidden_size, args.asn_hidden_size)
        self.env_info_rnn3 = nn.GRUCell(args.asn_hidden_size, args.asn_hidden_size)

        # no-op + stop + up, down, left, right
        self.wo_action_fc = nn.Linear(args.asn_hidden_size, 6)

        self.enemies_info_fc1 = nn.Linear(args.enemy_feats_size, args.asn_hidden_size)
        self.enemies_info_fc2 = nn.Linear(args.asn_hidden_size, args.asn_hidden_size)
        self.enemies_info_rnn3 = nn.GRUCell(args.asn_hidden_size, args.asn_hidden_size)

    def init_hidden(self):
        # make hidden states on same device as model
        return self.env_info_fc1.weight.new(1, self.args.asn_hidden_size * (1 + self.args.enemies_num)).zero_()

    def forward(self, inputs, hidden_state):
        # print(inputs.shape)
        # print(hidden_state.shape)


        enemies_feats = [inputs[:, self.enemies_feat_start + i * self.args.enemy_feats_size: self.enemies_feat_start + self.args.enemy_feats_size * (1 + i)]
                         for i in range(self.args.enemies_num)]

        # agents_feats = [inputs[:, self.agents_feat_start + i * 5: self.agents_feat_start + 5 * (1 + i)]
        #                 for i in range(self.args.agents_num - 1)]
        # self_input = th.cat([inputs[:, :self.move_feat_end],
        #                      inputs[:, self.blood_feat_start: self.blood_feat_end],
        #                      inputs[:, self.other_feat_start:]],
        #                     dim=1)

        h_in = th.split(hidden_state, self.args.asn_hidden_size, dim=-1)
        h_in_env = h_in[0].reshape(-1, self.args.asn_hidden_size)
        h_in_enemies = [_h.reshape(-1, self.args.asn_hidden_size) for _h in h_in[1:]]

        env_hidden_1 = F.relu(self.env_info_fc1(inputs))
        env_hidden_2 = self.env_info_fc2(env_hidden_1)
        h_env = self.env_info_rnn3(env_hidden_2, h_in_env)

        wo_action_fc_Q = self.wo_action_fc(h_env)

        enemies_hiddent_1 = [F.relu(self.enemies_info_fc1(enemy_info)) for enemy_info in enemies_feats]
        enemies_hiddent_2 = [self.enemies_info_fc2(enemy_info) for enemy_info in enemies_hiddent_1]
        enemies_h_hiddent_3 = [self.enemies_info_rnn3(enemy_info, enemy_h) for enemy_info, enemy_h in zip(enemies_hiddent_2, h_in_enemies)]

        attack_enemy_id_Q = [th.sum(h_env * enemy_info, dim=-1, keepdim=True) for enemy_info in enemies_h_hiddent_3]

        q = th.cat([wo_action_fc_Q, *attack_enemy_id_Q], dim=-1)
        hidden_state = th.cat([h_env, *enemies_h_hiddent_3], dim=-1)

        return q, hidden_state
